from datetime import date, datetime
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from adm.models import Credits
from adm.views import _shop_billing_rows, _shop_billing_schedule
from cupon.models import Shop


def local(day):
    return timezone.make_aware(datetime(2026, 10, day, 12))


class ShopBillingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('billing-staff', is_staff=True)
        self.shop = Shop.objects.create(
            name='Tienda', owner='Persona', phone='+52 833 123 4567',
            giro='Abarrotes', address='Calle', city='Tampico',
            seller=self.user, confirmation_date=local(5),
        )

    def movement(self, amount, day):
        credit = Credits.objects.create(customer=self.user, shop=self.shop, credits=amount)
        Credits.objects.filter(pk=credit.pk).update(date=local(day))

    def rows(self, query=None):
        request = RequestFactory().get('/', query or {})
        with patch('adm.views.timezone.localdate', return_value=date(2026, 10, 23)):
            return _shop_billing_rows(request)

    def test_only_debt_even_with_legacy_status_filter(self):
        self.assertEqual(self.rows(), [])
        self.movement(10, 6)
        self.assertEqual(self.rows(), [])
        self.movement(-110, 7)
        self.assertEqual(len(self.rows({'status': 'all'})), 1)
        self.assertEqual(len(self.rows({'status': 'current'})), 1)

    def test_weekly_schedule_and_partial_payment_keep_original_due_date(self):
        self.movement(-100, 6)
        self.movement(20, 20)
        row = self.rows()[0]
        self.assertEqual(row['payment_date'], date(2026, 10, 12))
        self.assertEqual(row['days_overdue'], 11)
        self.assertEqual(row['debt'], 80)
        self.assertEqual(row['debt_status'], 'atrasado')

    def test_settlement_then_new_debt_uses_next_weekly_due_date(self):
        self.movement(-100, 6)
        self.movement(100, 13)
        self.movement(-50, 20)
        row = self.rows()[0]
        self.assertEqual(row['payment_date'], date(2026, 10, 26))
        self.assertEqual(row['days_overdue'], 0)
        self.assertEqual(self.rows({'status': 'overdue'}), [])

    def test_phone_filter_handles_stored_format_and_partial_manual_input(self):
        self.movement(-100, 6)
        self.assertEqual(len(self.rows({'phone': '8331234567'})), 1)
        self.assertEqual(len(self.rows({'phone': '833'})), 1)
        self.assertEqual(self.rows({'phone': '999'}), [])

    def test_due_today_and_missing_activation(self):
        self.assertEqual(
            _shop_billing_schedule(local(5), local(6), date(2026, 10, 12)),
            (date(2026, 10, 12), 0),
        )
        self.assertEqual(_shop_billing_schedule(None, local(6), date(2026, 10, 23)), (None, 0))

    def test_page_and_exports_include_schedule(self):
        self.movement(-100, 6)
        self.user.is_superuser = True
        self.user.save(update_fields=['is_superuser'])
        self.client.force_login(self.user)
        with patch('adm.views.timezone.localdate', return_value=date(2026, 10, 23)):
            response = self.client.get(reverse('adm:shop_billing'))
            self.assertContains(response, 'Días de atraso')
            self.assertContains(response, '12/10/2026')
            csv = self.client.get(reverse('adm:shop_billing_export_excel'))
            self.assertContains(csv, '2026-10-12,11,atrasado')
            pdf = self.client.get(reverse('adm:shop_billing_export_pdf'))
            self.assertEqual(pdf.status_code, 200)
            self.assertIn(b'atraso 11 dias', pdf.content)
