from datetime import datetime
from django.test import Client, TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from adm.models import Account, Business, Service, Supplier, UserDetail, Sale
import json

class LoginAPITestCase(TestCase):
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass123', email='testuser@example.com')
        self.business = Business.objects.create(name="testbusiness")
        self.user_detail = UserDetail.objects.create(business=self.business, user=self.user, phone_number='1234567890', lada='123', 
                                                    country='Mexico', free_days=5)

    def test_valid_login(self):
        url = reverse('api:login_api')
        data = {
            "username": "testuser",
            "password": "testpass123"
        }
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertDictEqual(response.json()['user'], {"username": "testuser", "first_name": "", "last_name": "", "email": "testuser@example.com"})
        self.assertDictEqual(response.json()['detail'][0], {"phone_number": "1234567890", "lada": 123, "country": "Mexico", "free_days": 5})

    def test_invalid_login(self):
        url = reverse('api:login_api')
        data = {
            "username": "testuser",
            "password": "wrongpass"
        }
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertDictEqual(response.json(), {'detail': 'invalid username or password'})

    def test_invalid_method(self):
        url = reverse('api:login_api')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)
        self.assertDictEqual(response.json(), {'detail': 'method not allowed'})

class GetActiveAccountsTestCase(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='pass123')
        self.business = Business.objects.create(name="testbusiness")
        self.account_name = Service.objects.create(description="testaccount",perfil_quantity=3)
        self.supplier = Supplier.objects.create(name="testsupplier", business=self.business)
        self.account = Account.objects.create(account_name=self.account_name,business=self.business,created_by=self.user,modified_by=self.user,email="fsdf@fds.com",password="123456",pin="1234",profile=1,expiration_date=datetime.now(),supplier=self.supplier)
        self.sale = Sale.objects.create(status=True, customer=self.user, business=self.business,user_seller=self.user,account=self.account, expiration_date=datetime.now(),payment_amount=1000)

    def test_get_active_accounts(self):
        data = {
            'username': 'testuser',
            'password': 'pass123'
        }
        response = self.client.get(reverse('api:get_active_accounts'), data, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(str(response.content, encoding='utf8'), {'detail': [{'account__account_name__description': self.sale.account.account_name.description, 'account__email': self.sale.account.email, 'account__password': self.sale.account.password, 'account__pin': self.sale.account.pin, 'account__profile': self.sale.account.profile, 'expiration_date': self.sale.expiration_date}]})


    def test_get_active_accounts_invalid_credentials(self):
        data = {
            'username': 'testuser',
            'password': 'wrongpassword'
        }
        response = self.client.get(reverse('api:get_active_accounts'), data, content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_get_active_accounts_method_not_allowed(self):
        response = self.client.post(reverse('api:get_active_accounts'))
        self.assertEqual(response.status_code, 405)
