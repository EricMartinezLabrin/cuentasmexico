import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from adm.models import Business, UserDetail
from cupon.models import Shop


class PhoneOtpShopEligibilityTests(TestCase):
    def setUp(self):
        business = Business.objects.create(
            name='Test', email='test@example.com', url='https://example.com', phone_number='+528331234567'
        )
        user = User.objects.create_user(username='8331234567')
        shop = Shop.objects.create(
            name='Tienda', owner='Owner', phone='8331234567', giro='Test', address='Address',
            city='Monterrey', seller=user, status=True, confirmation=False,
        )
        UserDetail.objects.create(
            business=business, user=user, phone_number='8331234567', lada=52,
            country='Mexico', associated_shop=shop, is_shop_owner=True,
        )
        self.client = Client()

    @patch('api.phone_auth._send_whatsapp_otp')
    def test_does_not_send_otp_when_shop_is_not_approved(self, send_otp):
        response = self.client.post(
            reverse('api:phone_request_otp'),
            data=json.dumps({'phone': '+52 833-123-4567'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['code'], 'SHOP_NOT_ACTIVE_OR_APPROVED')
        send_otp.assert_not_called()
