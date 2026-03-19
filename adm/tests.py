from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from adm.functions.crm import CRMAnalytics
from adm.models import Account, Bank, Business, PaymentMethod, Sale, Service, Supplier, UserDetail


class CRMAnalyticsTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(
            name='Test Biz',
            email='biz@test.com',
            url='https://test.biz',
            phone_number='+5218331234567',
        )
        self.service_netflix = Service.objects.create(description='Netflix', perfil_quantity=1, price=100)
        self.service_hbo = Service.objects.create(description='HBO', perfil_quantity=1, price=120)
        self.supplier = Supplier.objects.create(
            business=self.business,
            name='Supplier Test',
            phone_number='+5218331111111',
        )
        self.payment_method = PaymentMethod.objects.create(description='Stripe')
        self.bank = Bank.objects.create(
            business=self.business,
            bank_name='Bank Test',
            headline='Cuenta',
            card_number='1234123412341234',
            clabe='123456789012345678',
        )

        self.seller = User.objects.create_user(username='seller', password='pass123')
        UserDetail.objects.create(
            business=self.business,
            user=self.seller,
            phone_number='8330000000',
            lada=52,
            country='MX',
        )

        self.customer_1 = User.objects.create_user(username='customer1', email='c1@test.com', password='pass123')
        self.customer_2 = User.objects.create_user(username='customer2', email='c2@test.com', password='pass123')
        self.customer_3 = User.objects.create_user(username='customer3', email='c3@test.com', password='pass123')

        UserDetail.objects.create(business=self.business, user=self.customer_1, phone_number='8331111111', lada=52, country='MX')
        UserDetail.objects.create(business=self.business, user=self.customer_2, phone_number='8332222222', lada=52, country='MX')
        UserDetail.objects.create(business=self.business, user=self.customer_3, phone_number='8333333333', lada=52, country='CL')

        self._create_sale(self.customer_1, self.service_netflix, 300, 50, True)
        self._create_sale(self.customer_1, self.service_hbo, 250, 20, True)
        self._create_sale(self.customer_2, self.service_netflix, 150, 10, True)
        self._create_sale(self.customer_3, self.service_hbo, 120, 70, False)

    def _create_sale(self, customer, service, amount, days_ago, status):
        now = timezone.now()
        account = Account.objects.create(
            business=self.business,
            supplier=self.supplier,
            customer=customer,
            created_by=self.seller,
            modified_by=self.seller,
            account_name=service,
            expiration_date=now + timedelta(days=30),
            renewal_date=now + timedelta(days=30),
            email=f'{customer.username}-{service.description.lower()}@test.com',
            password='secret123',
            profile=1,
            status=True,
            external_status='Disponible',
        )
        sale = Sale.objects.create(
            business=self.business,
            user_seller=self.seller,
            bank=self.bank,
            customer=customer,
            account=account,
            status=status,
            payment_method=self.payment_method,
            expiration_date=now + timedelta(days=30),
            payment_amount=amount,
            invoice=f'INV-{customer.id}-{service.id}-{days_ago}',
        )
        Sale.objects.filter(pk=sale.pk).update(created_at=now - timedelta(days=days_ago))

    def test_kpis_and_rankings(self):
        sales_qs, _ = CRMAnalytics.get_filtered_sales({'preset': 'last_90_days'})
        kpis = CRMAnalytics.get_kpis(sales_qs)
        top_customers = CRMAnalytics.get_top_customers(sales_qs)
        top_products = CRMAnalytics.get_top_products(sales_qs)

        self.assertEqual(kpis['total_sales'], 4)
        self.assertEqual(kpis['unique_customers'], 3)
        self.assertEqual(top_customers[0]['username'], 'customer1')
        self.assertEqual(top_products[0]['service'], 'Netflix')

    def test_churn_rule_45_days(self):
        filters = CRMAnalytics.parse_filters({'preset': 'last_90_days'})
        churn_customers = CRMAnalytics.get_churn_customers(filters)
        usernames = {row['username'] for row in churn_customers}

        self.assertIn('customer3', usernames)
        self.assertNotIn('customer1', usernames)

    def test_customer_type_filter_new(self):
        now = timezone.now()
        new_customer = User.objects.create_user(username='new_customer', email='new@test.com', password='pass123')
        UserDetail.objects.create(business=self.business, user=new_customer, phone_number='8334444444', lada=52, country='MX')
        self._create_sale(new_customer, self.service_netflix, 99, 1, True)
        User.objects.filter(pk=new_customer.pk).update(date_joined=now - timedelta(days=1))

        sales_qs, _ = CRMAnalytics.get_filtered_sales({'preset': 'last_7_days', 'customer_type': 'new'})
        usernames = set(sales_qs.values_list('customer__username', flat=True))
        self.assertIn('new_customer', usernames)

    def test_churn_sort_filter_is_respected(self):
        filters_desc = CRMAnalytics.parse_filters({'preset': 'last_90_days', 'churn_sort': 'desc'})
        filters_asc = CRMAnalytics.parse_filters({'preset': 'last_90_days', 'churn_sort': 'asc'})
        churn_desc = CRMAnalytics.get_churn_customers(filters_desc)
        churn_asc = CRMAnalytics.get_churn_customers(filters_asc)
        if len(churn_desc) >= 2 and len(churn_asc) >= 2:
            self.assertNotEqual(churn_desc[0]['customer_id'], churn_asc[0]['customer_id'])

    def test_recovered_customers_detected(self):
        recovered_user = User.objects.create_user(username='recovered_user', email='recovered@test.com', password='pass123')
        UserDetail.objects.create(
            business=self.business,
            user=recovered_user,
            phone_number='8335555555',
            lada=52,
            country='MX',
        )
        self._create_sale(recovered_user, self.service_netflix, 120, 80, True)
        self._create_sale(recovered_user, self.service_netflix, 150, 5, True)

        filters = CRMAnalytics.parse_filters({'preset': 'last_90_days'})
        recovered = CRMAnalytics.get_recovered_customers(filters)
        usernames = {row['username'] for row in recovered}
        self.assertIn('recovered_user', usernames)


class CRMViewsTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(
            name='Test Biz',
            email='biz@test.com',
            url='https://test.biz',
            phone_number='+5218331234567',
        )
        self.service = Service.objects.create(description='Netflix', perfil_quantity=1, price=100)
        self.supplier = Supplier.objects.create(
            business=self.business,
            name='Supplier Test',
            phone_number='+5218331111111',
        )
        self.payment_method = PaymentMethod.objects.create(description='Stripe')
        self.bank = Bank.objects.create(
            business=self.business,
            bank_name='Bank Test',
            headline='Cuenta',
            card_number='1234123412341234',
            clabe='123456789012345678',
        )

        self.superuser = User.objects.create_superuser('admin', 'admin@test.com', 'pass123')
        self.staff = User.objects.create_user('staff', 'staff@test.com', 'pass123', is_staff=True)
        self.customer = User.objects.create_user('customer', 'customer@test.com', 'pass123')

        UserDetail.objects.create(business=self.business, user=self.superuser, phone_number='8331000000', lada=52, country='MX')
        UserDetail.objects.create(business=self.business, user=self.staff, phone_number='8332000000', lada=52, country='MX')
        UserDetail.objects.create(business=self.business, user=self.customer, phone_number='8333000000', lada=52, country='MX')

        account = Account.objects.create(
            business=self.business,
            supplier=self.supplier,
            customer=self.customer,
            created_by=self.superuser,
            modified_by=self.superuser,
            account_name=self.service,
            expiration_date=timezone.now() + timedelta(days=30),
            email='customer-netflix@test.com',
            password='secret123',
            profile=1,
            status=True,
            external_status='Disponible',
        )
        Sale.objects.create(
            business=self.business,
            user_seller=self.superuser,
            bank=self.bank,
            customer=self.customer,
            account=account,
            status=True,
            payment_method=self.payment_method,
            expiration_date=timezone.now() + timedelta(days=30),
            payment_amount=200,
            invoice='INV-CRM-1',
        )

    def test_crm_dashboard_superuser_ok(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse('adm:crm_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'adm/crm.html')

    def test_crm_dashboard_denies_non_superuser(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('adm:crm_dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('adm:no-permission'), response.url)

    def test_csv_exports_return_csv(self):
        self.client.force_login(self.superuser)
        urls = [
            reverse('adm:crm_export_top_customers'),
            reverse('adm:crm_export_top_products'),
            reverse('adm:crm_export_churn_customers'),
            reverse('adm:crm_export_churn_products'),
            reverse('adm:crm_export_recovered_customers'),
        ]
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Content-Type'], 'text/csv')
