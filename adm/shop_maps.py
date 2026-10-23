"""Geocoding and portable itinerary helpers. No routing provider is required."""
import hashlib
import math
import time
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from cupon.models import ShopGeocodeCache, ShopGeocodeControl


class GeocodeError(Exception):
    pass


def coordinates(lat, lon):
    if isinstance(lat, bool) or isinstance(lon, bool):
        raise ValueError('Coordenadas invalidas.')
    lat, lon = float(lat), float(lon)
    if not math.isfinite(lat) or not math.isfinite(lon) or not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise ValueError('Coordenadas fuera de rango.')
    return {'lat': round(lat, 7), 'lng': round(lon, 7)}


def shop_address(shop):
    cp = str(shop.cp).zfill(5) if shop.cp is not None else ''
    return ', '.join(str(value).strip() for value in (shop.address, shop.city, cp, 'Mexico') if value)


def geocode(query):
    query = ' '.join(query.split())
    if not 3 <= len(query) <= 600:
        raise ValueError('Ingresa una direccion de 3 a 600 caracteres.')
    endpoint = settings.SHOP_GEOCODER_URL
    key = hashlib.sha256((endpoint + '|' + query.casefold()).encode()).hexdigest()
    cached = ShopGeocodeCache.objects.filter(key=key).first()
    if cached:
        return cached.results
    ShopGeocodeControl.objects.get_or_create(pk=1)
    # Keep the singleton lock through the outbound request: all workers share the limit.
    with transaction.atomic():
        control = ShopGeocodeControl.objects.select_for_update().get(pk=1)
        cached = ShopGeocodeCache.objects.filter(key=key).first()
        if cached:
            return cached.results
        if control.last_request_at:
            delay = 1.1 - (timezone.now() - control.last_request_at).total_seconds()
            if delay > 0:
                time.sleep(delay)
        error = None
        results = []
        try:
            response = requests.get(endpoint, params={'q': query, 'format': 'jsonv2', 'limit': 5, 'countrycodes': 'mx'},
                                    headers={'User-Agent': settings.SHOP_GEOCODER_USER_AGENT}, timeout=15)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list):
                raise ValueError('Respuesta invalida')
            for item in payload:
                point = coordinates(item['lat'], item['lon'])
                results.append({**point, 'label': str(item.get('display_name', ''))[:600]})
            ShopGeocodeCache.objects.create(key=key, query=query, results=results)
        except (requests.RequestException, ValueError, KeyError, TypeError):
            error = GeocodeError('No se pudo consultar el proveedor. Intenta mas tarde.')
        control.last_request_at = timezone.now()
        control.save(update_fields=['last_request_at'])
    # Raise after commit so failures also retain the shared throttle timestamp.
    if error:
        raise error
    return results


def distance(a, b):
    lat1, lat2 = math.radians(a['lat']), math.radians(b['lat'])
    dl = math.radians(b['lng'] - a['lng'])
    h = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dl/2)**2
    return 2 * 6371 * math.asin(min(1, math.sqrt(h)))


def nearest_order(origin, stops):
    remaining = list(stops)
    result = []
    current = origin
    while remaining:
        index = min(range(len(remaining)), key=lambda i: (distance(current, remaining[i]), remaining[i]['id']))
        current = remaining.pop(index)
        result.append(current)
    return result


def google_segments(itinerary):
    stops = list(itinerary['stops'])
    if itinerary['return_to_origin']:
        stops.append(itinerary['origin'])
    start = itinerary['origin']
    segments = []
    for index in range(0, len(stops), 4):
        group = stops[index:index+4]
        point = lambda p: f"{p['lat']},{p['lng']}"
        params = {'api': 1, 'origin': point(start), 'destination': point(group[-1]), 'travelmode': 'driving', 'dir_action': 'navigate'}
        if len(group) > 1:
            params['waypoints'] = '|'.join(point(p) for p in group[:-1])
        url = 'https://www.google.com/maps/dir/?' + urlencode(params)
        if len(url) > 2048:
            raise ValueError('El tramo excede el limite de Google Maps.')
        segments.append({'number': len(segments)+1, 'url': url})
        start = group[-1]
    return segments
