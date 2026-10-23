"""Staff-only map endpoints and a deliberately minimal public route page."""
import json
import secrets
from datetime import timedelta
from functools import wraps

from django.conf import settings
from django.db import transaction
from django.db.models import Max, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.cache import never_cache

from adm.models import Credits
from cupon.models import Shop, ShopGeocodeControl, ShopVisitRoute
from .shop_maps import GeocodeError, coordinates, geocode, google_segments, nearest_order, shop_address


def staff(view):
    @wraps(view)
    @never_cache
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated or not (request.user.is_staff or request.user.is_superuser):
            return JsonResponse({'error': 'Acceso exclusivo para personal autorizado.'}, status=403)
        try:
            return view(request, *args, **kwargs)
        except (ValueError, TypeError, KeyError, OverflowError):
            return JsonResponse({'error': 'Datos invalidos. Revisa coordenadas y seleccion.'}, status=400)
        except GeocodeError as exc:
            return JsonResponse({'error': str(exc)}, status=502)
    return wrapped


def body(request):
    value = json.loads(request.body or b'{}')
    if not isinstance(value, dict):
        raise ValueError()
    return value


def map_settings():
    return {'tiles': settings.SHOP_MAP_TILE_URL, 'attribution': settings.SHOP_MAP_ATTRIBUTION}


def state(shop):
    return 'pending' if not shop.confirmation else ('active' if shop.status else 'suspended')


@staff
@require_GET
def map_config(request):
    return JsonResponse(map_settings())


@staff
@require_GET
def map_page(request):
    return render(request, 'adm/shop_map.html', {'map_settings': map_settings()})


@staff
@require_GET
def map_data(request):
    shops = Shop.objects.all().order_by('id')
    states = request.GET.getlist('state') or ['active']
    clauses = Q()
    for name in states:
        if name == 'active':
            clauses |= Q(status=True, confirmation=True)
        elif name == 'suspended':
            clauses |= Q(status=False, confirmation=True)
        elif name == 'pending':
            clauses |= Q(confirmation=False)
        else:
            raise ValueError()
    shops = shops.filter(clauses)
    query = request.GET.get('q', '').strip()
    if query:
        search = Q(name__icontains=query) | Q(owner__icontains=query) | Q(email__icontains=query)
        phone = ''.join(ch for ch in query if ch.isdigit())
        if len(phone) >= 10:
            search |= Q(phone__icontains=phone[-10:])
        shops = shops.filter(search)
    if request.GET.get('city'):
        shops = shops.filter(city__icontains=request.GET['city'])
    if request.GET.get('cp'):
        shops = shops.filter(cp=int(request.GET['cp']))
    location = request.GET.get('location', '')
    if location == 'confirmed':
        shops = shops.filter(location_confirmed=True, latitude__isnull=False, longitude__isnull=False)
    elif location == 'approximate':
        shops = shops.filter(location_confirmed=False, latitude__isnull=False, longitude__isnull=False)
    elif location == 'missing':
        shops = shops.filter(Q(latitude__isnull=True) | Q(longitude__isnull=True))
    rows = []
    for shop in shops:
        point = coordinates(shop.latitude, shop.longitude) if shop.latitude is not None and shop.longitude is not None else None
        rows.append({'id': shop.id, 'name': shop.name, 'city': shop.city, 'state': state(shop), 'point': point,
                     'confirmed': shop.location_confirmed, 'address': shop_address(shop)})
    return JsonResponse({'shops': rows})


@staff
@require_GET
def map_detail(request, pk):
    shop = get_object_or_404(Shop.objects.select_related('location_reviewed_by'), pk=pk)
    balance = Credits.objects.filter(shop=shop).aggregate(total=Sum('credits'))['total'] or 0
    return JsonResponse({'id': shop.id, 'name': shop.name, 'owner': shop.owner, 'phone': shop.phone,
        'email': shop.email or '', 'giro': shop.giro, 'address': shop.address, 'city': shop.city, 'cp': shop.cp,
        'state': state(shop), 'balance': str(balance), 'credit_limit': shop.credit_limit,
        'available': str(shop.credit_limit + balance), 'confirmation_date': shop.confirmation_date,
        'comision_date': shop.comision_date, 'last_negative_balance_since': shop.last_negative_balance_since,
        'consecutive_on_time_payments': shop.consecutive_on_time_payments,
        'location_source': shop.location_source, 'location_confirmed': shop.location_confirmed,
        'location_reviewed_at': shop.location_reviewed_at,
        'location_reviewed_by': shop.location_reviewed_by.get_username() if shop.location_reviewed_by else None,
        'point': coordinates(shop.latitude, shop.longitude) if shop.latitude is not None and shop.longitude is not None else None,
        'detail_url': reverse('adm:shop_detail', args=[shop.id])})


@staff
@require_POST
def search_location(request):
    data = body(request)
    if data.get('shop_id'):
        shop = get_object_or_404(Shop, pk=int(data['shop_id']))
        query = shop_address(shop)
    else:
        query = str(data.get('address', ''))
    return JsonResponse({'results': geocode(query)})


@staff
@require_POST
def save_location(request, pk):
    data = body(request)
    point = coordinates(data['lat'], data['lng'])
    if not isinstance(data.get('confirmed'), bool):
        raise ValueError()
    with transaction.atomic():
        shop = get_object_or_404(Shop.objects.select_for_update(), pk=pk)
        shop.latitude, shop.longitude = point['lat'], point['lng']
        shop.location_source = 'manual'
        shop.location_confirmed = data['confirmed']
        shop.location_reviewed_at = timezone.now() if data['confirmed'] else None
        shop.location_reviewed_by = request.user if data['confirmed'] else None
        shop.save(update_fields=['latitude', 'longitude', 'location_source', 'location_confirmed', 'location_reviewed_at', 'location_reviewed_by'])
    return JsonResponse({'ok': True})


def batch_info(control):
    return {'started': control.batch_started, 'finished': control.batch_finished,
            'processed': control.batch_processed, 'total': control.batch_total, 'errors': control.batch_errors}


@staff
@require_GET
def batch_status(request):
    control = ShopGeocodeControl.objects.filter(pk=1).first()
    return JsonResponse(batch_info(control) if control else {'started': False, 'finished': False, 'processed': 0, 'total': 0, 'errors': []})


@staff
@require_POST
def batch_step(request):
    ShopGeocodeControl.objects.get_or_create(pk=1)
    now = timezone.now()
    with transaction.atomic():
        control = ShopGeocodeControl.objects.select_for_update().get(pk=1)
        if control.batch_finished:
            return JsonResponse(batch_info(control))
        if control.batch_running_until and control.batch_running_until > now:
            return JsonResponse({'error': 'Lote ocupado. Reanuda en un minuto.'}, status=409)
        if not control.batch_started:
            missing = Shop.objects.filter(Q(latitude__isnull=True) | Q(longitude__isnull=True))
            total = missing.count()
            limit = settings.SHOP_GEOCODE_INITIAL_LIMIT
            if 'nominatim.openstreetmap.org' in settings.SHOP_GEOCODER_URL:
                limit = min(limit, 100)
            if total > limit:
                return JsonResponse({'error': 'Volumen superior al lote publico pequeno. Configura otro proveedor antes de continuar.'}, status=400)
            control.batch_started = True
            control.batch_total = total
            control.batch_max_id = Shop.objects.aggregate(value=Max('id'))['value'] or 0
        shop = Shop.objects.filter(pk__gt=control.batch_cursor, pk__lte=control.batch_max_id).filter(
            Q(latitude__isnull=True) | Q(longitude__isnull=True)).order_by('id').first()
        if not shop:
            control.batch_finished = True
            control.batch_running_until = None
            control.save()
            return JsonResponse(batch_info(control))
        control.batch_running_until = now + timedelta(seconds=60)
        control.save()
    error = None
    try:
        results = geocode(shop_address(shop))
    except GeocodeError:
        # Keep cursor for a resumable transient failure.
        ShopGeocodeControl.objects.filter(pk=1).update(batch_running_until=None)
        raise
    except ValueError:
        results = []
    with transaction.atomic():
        control = ShopGeocodeControl.objects.select_for_update().get(pk=1)
        current = Shop.objects.select_for_update().filter(pk=shop.id).first()
        if current and shop_address(current) == shop_address(shop) and not current.location_confirmed and (current.latitude is None or current.longitude is None):
            if len(results) == 1:
                current.latitude, current.longitude = results[0]['lat'], results[0]['lng']
                current.location_source = 'nominatim'
                current.save(update_fields=['latitude', 'longitude', 'location_source'])
            else:
                error = {'id': shop.id, 'reason': 'Sin resultados' if not results else 'Direccion ambigua'}
        if error:
            control.batch_errors = control.batch_errors + [error]
        control.batch_cursor = shop.id
        control.batch_processed += 1
        control.batch_running_until = None
        control.save()
    return JsonResponse(batch_info(control))


@staff
@require_POST
def route_create(request):
    data = body(request)
    ids = data.get('shops')
    if not isinstance(ids, list) or not ids or len(ids) > 500 or any(type(pk) is not int for pk in ids) or len(set(ids)) != len(ids):
        raise ValueError()
    origin = coordinates(data['origin']['lat'], data['origin']['lng'])
    if type(data.get('return_to_origin')) is not bool or data.get('order') not in ('manual', 'nearest'):
        raise ValueError()
    shops = Shop.objects.in_bulk(ids)
    if len(shops) != len(ids):
        raise ValueError()
    stops = []
    for pk in ids:
        shop = shops[pk]
        if not shop.location_confirmed or shop.latitude is None or shop.longitude is None:
            return JsonResponse({'error': f'Confirma la ubicacion de {shop.name} antes de crear ruta.'}, status=400)
        stops.append({'id': pk, 'name': shop.name, **coordinates(shop.latitude, shop.longitude)})
    if data['order'] == 'nearest':
        stops = nearest_order(origin, stops)
    itinerary = {'origin': origin, 'stops': stops, 'return_to_origin': data['return_to_origin']}
    # Validate before persisting. Itinerary is a snapshot, never serialized from live shops publicly.
    google_segments(itinerary)
    route = ShopVisitRoute.objects.create(token=secrets.token_urlsafe(32), created_by=request.user,
        expires_at=timezone.now()+timedelta(days=7), itinerary=itinerary)
    return JsonResponse({'url': request.build_absolute_uri(reverse('adm:shop_route_public', args=[route.token])),
        'id': route.pk, 'expires_at': route.expires_at}, status=201)


@staff
@require_GET
def route_list(request):
    rows = [{'id': row.pk, 'created_at': row.created_at, 'expires_at': row.expires_at, 'revoked': row.revoked_at is not None,
             'url': request.build_absolute_uri(reverse('adm:shop_route_public', args=[row.token]))}
            for row in ShopVisitRoute.objects.order_by('-id')[:100]]
    return JsonResponse({'routes': rows})


@staff
@require_POST
def route_revoke(request, pk):
    route = get_object_or_404(ShopVisitRoute, pk=pk)
    route.revoked_at = timezone.now()
    route.save(update_fields=['revoked_at'])
    return JsonResponse({'ok': True})


@never_cache
@require_GET
def route_public(request, token):
    route = get_object_or_404(ShopVisitRoute, token=token)
    if route.revoked_at or route.expires_at <= timezone.now():
        return render(request, 'adm/shop_route_public.html', {'unavailable': True}, status=410)
    # Whitelist fields: no shop lookup, identity, contact, finance or administrative URLs.
    itinerary = {'origin': coordinates(route.itinerary['origin']['lat'], route.itinerary['origin']['lng']),
        'stops': [{'name': stop['name'], 'lat': stop['lat'], 'lng': stop['lng']} for stop in route.itinerary['stops']],
        'return_to_origin': route.itinerary['return_to_origin']}
    response = render(request, 'adm/shop_route_public.html', {'itinerary': itinerary, 'segments': google_segments(itinerary),
        'expires_at': route.expires_at, 'map_settings': map_settings()})
    response['X-Robots-Tag'] = 'noindex, nofollow'
    response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response
