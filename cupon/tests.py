from django.contrib.auth.models import User
from django.test import TestCase

from adm.models import Business, UserDetail
from cupon.models import Cupon, CouponRedemption
from cupon.services import CouponRedeemError, consume_coupon, validate_coupon_for_customer


class CouponPhoneRulesTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(
            name='CM',
            email='cm@test.com',
            url='https://example.com',
            phone_number='+525551111111',
        )

    def _create_user_with_phone(self, username, phone='5512345678', lada=52):
        user = User.objects.create_user(username=username, password='secret123')
        UserDetail.objects.create(
            business=self.business,
            user=user,
            phone_number=phone,
            lada=lada,
            country='Mexico',
        )
        return user

    def test_blocks_reuse_by_same_phone_across_accounts(self):
        first_user = self._create_user_with_phone('first')
        second_user = self._create_user_with_phone('second')

        coupon = Cupon.objects.create(
            name='phone-test',
            long=1,
            price=100,
            folder=1,
            max_uses=5,
        )

        consume_coupon('phone-test', first_user, channel=CouponRedemption.CHANNEL_WEB)

        with self.assertRaises(CouponRedeemError):
            validate_coupon_for_customer(coupon, second_user)

    def test_consume_coupon_updates_counter_and_log(self):
        user = self._create_user_with_phone('single')
        coupon = Cupon.objects.create(
            name='single-use',
            long=1,
            price=120,
            folder=2,
            max_uses=1,
        )

        consume_coupon('single-use', user, channel=CouponRedemption.CHANNEL_WEB)

        coupon.refresh_from_db()
        self.assertEqual(coupon.used_count, 1)
        self.assertEqual(CouponRedemption.objects.filter(cupon=coupon).count(), 1)
