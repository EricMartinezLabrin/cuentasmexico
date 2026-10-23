"""Regression tests for location safety, map access, initial batch and public routes."""
import importlib
import json
from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

import requests
from django.contrib.auth.models import User
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from adm.models import Credits
from adm.shop_maps import GeocodeError, coordinates, geocode, google_segments, nearest_order
from cupon.forms import ShopForm
from cupon.models import Shop, ShopGeocodeCache, ShopGeocodeControl, ShopVisitRoute


class RouteHelpersTests(SimpleTestCase):
    def test_coordinate_validation(self):
        for lat, lng in [(91, 0), (0, -181), ('nan', 1), ('inf', 1), (True, 0)]:
            with self.subTest(lat=lat), self.assertRaises((ValueError, TypeError)):
                coordinates(lat, lng)
        self.assertEqual(coordinates('19.1', '-99.2'), {'lat': 19.1, 'lng': -99.2})

    def test_nearest_order(self):
        stops = [{'id': 1, 'lat': 22, 'lng': -99}, {'id': 2, 'lat': 19.1, 'lng': -99}]
        self.assertEqual([p['id'] for p in nearest_order({'lat': 19, 'lng': -99}, stops)], [2, 1])

    def test_segments_keep_every_stop_and_return(self):
        origin = {'lat': 19, 'lng': -99}
        stops = [{'lat': 19+i/100, 'lng': -99} for i in range(1, 15)]
        data = {'origin': origin, 'stops': stops, 'return_to_origin': True}
        segments = google_segments(data)
        all_stops, previous = [], '19,-99'
        for row in segments:
            params = parse_qs(urlsplit(row['url']).query)
            self.assertEqual(params['origin'][0], previous)
            intermediate = params.get('waypoints', [''])[0].split('|') if 'waypoints' in params else []
            self.assertLessEqual(len(intermediate), 3)
            all_stops.extend(intermediate + params['destination'])
            previous = params['destination'][0]
            self.assertLessEqual(len(row['url']), 2048)
        self.assertEqual(all_stops, [f"{p['lat']},{p['lng']}" for p in stops+[origin]])

    def test_new_migration_contains_only_feature_operations(self):
        migration = importlib.import_module('cupon.migrations.0008_shopgeocodecache_shopgeocodecontrol_and_more').Migration
        from django.db.migrations import AddField, CreateModel
        self.assertEqual(len(migration.operations), 9)
        for operation in migration.operations:
            self.assertIsInstance(operation, (AddField, CreateModel))
            if isinstance(operation, AddField):
                self.assertEqual(operation.model_name, 'shop')
                self.assertIn(operation.name, ('latitude','longitude','location_source','location_confirmed','location_reviewed_at','location_reviewed_by'))


class MapFeatureTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('staff', is_staff=True)
        self.client.force_login(self.user)
        self.shop = self.make_shop('Tienda uno', location_confirmed=True, latitude=19.1, longitude=-99.2)

    def make_shop(self, name, **kwargs):
        values = dict(name=name, owner='Dueño privado', phone='8331234567', email='privado@example.com',
            giro='Abarrotes', address='Calle Comercial 10', city='Tampico', cp=89000, seller=self.user, status=True, confirmation=True)
        values.update(kwargs)
        return Shop.objects.create(**values)

    def post(self, name, data=None, args=()):
        return self.client.post(reverse('adm:'+name, args=args), json.dumps(data or {}), content_type='application/json')

    def test_map_page_and_form_templates_render(self):
        response = self.client.get(reverse('adm:shop_map'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Mapa de calor')
        self.user.is_superuser = True
        self.user.save(update_fields=['is_superuser'])
        self.assertEqual(self.client.get(reverse('adm:shop_create')).status_code, 200)

    def test_states_and_no_pagination(self):
        for i in range(28):
            self.make_shop(f'Extra {i}')
        suspended = self.make_shop('Suspendida', status=False)
        pending = self.make_shop('Pendiente', status=False, confirmation=False)
        url = reverse('adm:shop_map_data')
        self.assertEqual(len(self.client.get(url).json()['shops']), 29)
        self.assertEqual([s['id'] for s in self.client.get(url, {'state':['suspended']}).json()['shops']], [suspended.pk])
        self.assertEqual([s['id'] for s in self.client.get(url, {'state':['pending']}).json()['shops']], [pending.pk])
        self.assertEqual(len(self.client.get(url, {'state':['active','pending','suspended']}).json()['shops']),31)

    def test_filters_and_missing_approximate_locations(self):
        self.make_shop('Sin pin', city='Monterrey')
        approximate = self.make_shop('Aproximada', latitude=20, longitude=-99)
        url = reverse('adm:shop_map_data')
        self.assertEqual(len(self.client.get(url, {'location':'missing'}).json()['shops']),1)
        self.assertEqual([s['id'] for s in self.client.get(url, {'location':'approximate'}).json()['shops']],[approximate.pk])
        self.assertEqual(len(self.client.get(url, {'city':'Tampico','cp':'89000','q':'+52 833 123 4567'}).json()['shops']),2)

    def test_detail_read_does_not_adjust_balances_or_bank(self):
        Credits.objects.create(shop=self.shop, customer=self.user, credits=-75)
        response = self.client.get(reverse('adm:shop_map_detail',args=[self.shop.pk]))
        self.assertEqual(response.json()['balance'],'-75')
        self.assertEqual(response.json()['available'],'225')
        self.shop.refresh_from_db()
        self.assertIsNone(self.shop.last_negative_balance_since)
        self.assertIsNone(self.shop.payment_bank_id)

    def test_access_and_post_only(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse('adm:shop_map_data')).status_code,403)
        self.client.force_login(User.objects.create_user('customer'))
        self.assertEqual(self.post('shop_map_route_create').status_code,403)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('adm:shop_map_location',args=[self.shop.pk])).status_code,405)
        csrf_client=Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        self.assertEqual(csrf_client.post(reverse('adm:shop_map_location',args=[self.shop.pk]), '{}',content_type='application/json').status_code,403)

    def test_save_location_and_validation(self):
        bad=self.post('shop_map_location',{'lat':95,'lng':1,'confirmed':True},args=[self.shop.pk])
        self.assertEqual(bad.status_code,400)
        for lat in (None,'nan',True):
            self.assertEqual(self.post('shop_map_location',{'lat':lat,'lng':1,'confirmed':True},args=[self.shop.pk]).status_code,400)
        good=self.post('shop_map_location',{'lat':19.5,'lng':-99.1,'confirmed':True},args=[self.shop.pk])
        self.assertEqual(good.status_code,200)
        self.shop.refresh_from_db()
        self.assertTrue(self.shop.location_confirmed)
        self.assertEqual(self.shop.location_reviewed_by,self.user)

    def test_address_change_invalidates_confirmation_even_partial_save(self):
        self.shop.address='Otra calle'
        self.shop.save(update_fields=['address'])
        self.shop.refresh_from_db()
        self.assertFalse(self.shop.location_confirmed)
        self.assertIsNone(self.shop.location_reviewed_at)

    def test_form_manual_coordinates_and_confirmation(self):
        data={key:getattr(self.shop,key) for key in ('name','owner','phone','email','giro','address','city','cp','credit_limit')}
        data.update(latitude='20',longitude='-99',confirm_location='on')
        form=ShopForm(data,instance=self.shop,location_user=self.user)
        self.assertTrue(form.is_valid(),form.errors)
        saved=form.save()
        self.assertTrue(saved.location_confirmed)
        self.assertEqual(saved.location_reviewed_by,self.user)
        data['latitude']='999'
        self.assertFalse(ShopForm(data,instance=saved).is_valid())

    def route(self, **kwargs):
        data={'origin':{'lat':19,'lng':-99},'shops':[self.shop.id],'return_to_origin':False,'order':'manual'}
        data.update(kwargs)
        return self.post('shop_map_route_create',data)

    def test_unconfirmed_and_duplicate_stops_rejected(self):
        approx=self.make_shop('No confirmada',latitude=20,longitude=-99)
        self.assertEqual(self.route(shops=[approx.pk]).status_code,400)
        self.assertEqual(self.route(shops=[self.shop.pk,self.shop.pk]).status_code,400)
        self.assertEqual(self.route(shops=[]).status_code,400)

    def test_public_snapshot_private_fields_absent_and_revocation(self):
        result=self.route()
        self.assertEqual(result.status_code,201,result.content)
        route=ShopVisitRoute.objects.get(pk=result.json()['id'])
        self.assertAlmostEqual((route.expires_at-route.created_at).total_seconds(),7*86400,delta=2)
        self.shop.name='Nombre nuevo'
        self.shop.save()
        self.client.logout()
        page=self.client.get(reverse('adm:shop_route_public',args=[route.token]))
        self.assertEqual(page.status_code,200)
        self.assertContains(page,'Tienda uno')
        for private in ('Dueño privado','8331234567','privado@example.com','Nombre nuevo','credit_limit','detail_url','created_by'):
            self.assertNotContains(page,private)
        self.assertNotIn('id',page.context['itinerary']['stops'][0])
        self.client.force_login(self.user)
        self.assertEqual(self.post('shop_map_route_revoke',args=[route.pk]).status_code,200)
        self.client.logout()
        self.assertEqual(self.client.get(reverse('adm:shop_route_public',args=[route.token])).status_code,410)

    def test_expired_route(self):
        r=self.route().json()
        ShopVisitRoute.objects.filter(pk=r['id']).update(expires_at=timezone.now()-timedelta(seconds=1))
        self.assertEqual(self.client.get(r['url']).status_code,410)

    @patch('adm.shop_map_views.geocode')
    def test_batch_resumes_preserves_confirmed_and_marks_approximate(self, lookup):
        target=self.make_shop('Sin coordenadas')
        lookup.return_value=[{'lat':21,'lng':-99,'label':'Resultado'}]
        first=self.post('shop_map_batch_step')
        self.assertEqual(first.status_code,200,first.content)
        target.refresh_from_db()
        self.assertEqual(target.latitude,Decimal('21'))
        self.assertFalse(target.location_confirmed)
        self.shop.refresh_from_db()
        self.assertEqual(self.shop.latitude,Decimal('19.1'))
        self.assertTrue(self.post('shop_map_batch_step').json()['finished'])
        self.post('shop_map_batch_step')
        self.assertEqual(lookup.call_count,1)

    @patch('adm.shop_map_views.geocode')
    def test_batch_ambiguous_results_remain_missing(self,lookup):
        target=self.make_shop('Ambigua')
        lookup.return_value=[{'lat':21,'lng':-99},{'lat':22,'lng':-99}]
        result=self.post('shop_map_batch_step')
        self.assertEqual(len(result.json()['errors']),1)
        target.refresh_from_db()
        self.assertIsNone(target.latitude)

    @override_settings(SHOP_GEOCODE_INITIAL_LIMIT=0)
    def test_batch_volume_guard(self):
        self.make_shop('Sin ubicacion')
        self.assertEqual(self.post('shop_map_batch_step').status_code,400)
        self.assertFalse(ShopGeocodeControl.objects.get(pk=1).batch_started)

    @patch('adm.shop_map_views.geocode',side_effect=GeocodeError('Proveedor no disponible'))
    def test_batch_transient_failure_is_resumable(self,lookup):
        self.make_shop('Pendiente localizar')
        self.assertEqual(self.post('shop_map_batch_step').status_code,502)
        control=ShopGeocodeControl.objects.get(pk=1)
        self.assertEqual(control.batch_cursor,0)
        self.assertIsNone(control.batch_running_until)

    @patch('adm.shop_maps.requests.get')
    @patch('adm.shop_maps.time.sleep')
    def test_geocoding_cache_and_shared_rate_limit(self,sleep,get):
        get.return_value=Mock(json=lambda:[{'lat':'19','lon':'-99','display_name':'Direccion'}],raise_for_status=lambda:None)
        geocode('Calle Comercial, Tampico')
        geocode('calle comercial, Tampico')
        self.assertEqual(get.call_count,1)
        geocode('Otra Calle, Tampico')
        self.assertEqual(get.call_count,2)
        self.assertTrue(sleep.called)
        self.assertEqual(ShopGeocodeCache.objects.count(),2)
        self.assertNotIn('Dueño',str(get.call_args))

    @patch('adm.shop_maps.requests.get',side_effect=requests.Timeout())
    def test_failed_lookup_keeps_rate_timestamp_and_does_not_cache(self,get):
        with self.assertRaises(GeocodeError):
            geocode('Calle Comercial, Tampico')
        self.assertIsNotNone(ShopGeocodeControl.objects.get(pk=1).last_request_at)
        self.assertEqual(ShopGeocodeCache.objects.count(),0)
