from django.db import models
from adm.models import Sale
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from dateutil.relativedelta import relativedelta

class Shop(models.Model):
    name = models.CharField(max_length=200)
    owner = models.CharField(max_length=200)
    phone = models.CharField(max_length=200)
    email = models.EmailField(blank=True, null=True)
    giro = models.CharField(max_length=200)
    confirmation = models.BooleanField(default=False)
    comision = models.BooleanField(default=False)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=200)
    cp = models.IntegerField(blank=True,null=True)
    confirmation_date = models.DateTimeField(blank=True,null=True)
    comision_date = models.DateTimeField(blank=True,null=True)
    seller = models.ForeignKey(User,on_delete=models.CASCADE)
    status = models.BooleanField(default=True)
    image = models.FileField(upload_to="shop/", null=True, blank=True)

class Cupon(models.Model):
    DURATION_UNIT_DAY = 'day'
    DURATION_UNIT_WEEK = 'week'
    DURATION_UNIT_MONTH = 'month'
    DURATION_UNIT_YEAR = 'year'

    DURATION_UNIT_CHOICES = [
        (DURATION_UNIT_DAY, 'Día'),
        (DURATION_UNIT_WEEK, 'Semana'),
        (DURATION_UNIT_MONTH, 'Mes'),
        (DURATION_UNIT_YEAR, 'Año'),
    ]

    name = models.CharField(max_length=30, unique=True)
    status = models.BooleanField(default=True)
    long = models.IntegerField()
    duration_unit = models.CharField(max_length=10, choices=DURATION_UNIT_CHOICES, default=DURATION_UNIT_MONTH)
    duration_quantity = models.PositiveIntegerField(default=1)
    requires_duration_review = models.BooleanField(default=False)
    max_uses = models.PositiveIntegerField(default=1)
    used_count = models.PositiveIntegerField(default=0)
    one_use_per_phone = models.BooleanField(default=True)
    price = models.IntegerField()
    folder = models.IntegerField()
    create_date = models.DateTimeField(auto_now=True)
    used_at = models.DateTimeField(blank=True, null=True)
    customer = models.ForeignKey(User,on_delete=models.CASCADE, related_name='customer', null=True,blank=True)
    seller = models.ForeignKey(User,on_delete=models.CASCADE, related_name='seller', null=True, blank = True)
    order = models.ForeignKey(Sale, on_delete=models.CASCADE, null=True, blank = True)
    status_payment = models.BooleanField(default=False)
    status_sale = models.BooleanField(default=False)  
    shop = models.ForeignKey(Shop,on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['status'], name='cupon_status_idx'),
            models.Index(fields=['used_count', 'max_uses'], name='cupon_uses_idx'),
        ]

    def __str__(self):
        return self.name

    @property
    def remaining_uses(self):
        if self.max_uses == 0:
            return None
        remaining = self.max_uses - self.used_count
        return remaining if remaining > 0 else 0

    @property
    def is_exhausted(self):
        if self.max_uses == 0:
            return False
        return self.used_count >= self.max_uses

    def can_redeem(self):
        return self.status and not self.is_exhausted

    def duration_delta(self):
        if self.duration_unit == self.DURATION_UNIT_DAY:
            return timedelta(days=self.duration_quantity)
        if self.duration_unit == self.DURATION_UNIT_WEEK:
            return timedelta(weeks=self.duration_quantity)
        if self.duration_unit == self.DURATION_UNIT_YEAR:
            return relativedelta(years=self.duration_quantity)
        return relativedelta(months=self.duration_quantity)

    def get_expiration_date(self, base_date=None):
        base_date = base_date or timezone.now()
        return base_date + self.duration_delta()

    def duration_in_months_approx(self):
        if self.duration_unit == self.DURATION_UNIT_DAY:
            return max(1, round(self.duration_quantity / 30))
        if self.duration_unit == self.DURATION_UNIT_WEEK:
            return max(1, round((self.duration_quantity * 7) / 30))
        if self.duration_unit == self.DURATION_UNIT_YEAR:
            return self.duration_quantity * 12
        return self.duration_quantity

    @property
    def duration_text(self):
        qty = self.duration_quantity
        if self.duration_unit == self.DURATION_UNIT_DAY:
            unit = 'día' if qty == 1 else 'días'
        elif self.duration_unit == self.DURATION_UNIT_WEEK:
            unit = 'semana' if qty == 1 else 'semanas'
        elif self.duration_unit == self.DURATION_UNIT_YEAR:
            unit = 'año' if qty == 1 else 'años'
        else:
            unit = 'mes' if qty == 1 else 'meses'
        return f"{qty} {unit}"


class CouponRedemption(models.Model):
    CHANNEL_WEB = 'web'
    CHANNEL_ADMIN = 'admin'

    CHANNEL_CHOICES = [
        (CHANNEL_WEB, 'Web'),
        (CHANNEL_ADMIN, 'Admin'),
    ]

    cupon = models.ForeignKey(Cupon, on_delete=models.CASCADE, related_name='redemptions')
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='coupon_redemptions')
    sale = models.ForeignKey(Sale, on_delete=models.SET_NULL, null=True, blank=True, related_name='coupon_redemptions')

    channel = models.CharField(max_length=10, choices=CHANNEL_CHOICES)
    service_name = models.CharField(max_length=120, blank=True, null=True)
    account_email = models.EmailField(blank=True, null=True)
    profile = models.IntegerField(blank=True, null=True)
    payment_amount = models.IntegerField(blank=True, null=True)
    duration_unit = models.CharField(max_length=10, choices=Cupon.DURATION_UNIT_CHOICES)
    duration_quantity = models.PositiveIntegerField(default=1)

    phone_lada = models.IntegerField(blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    phone_key = models.CharField(max_length=32, blank=True, null=True)
    redeemed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-redeemed_at']
        indexes = [
            models.Index(fields=['cupon', 'redeemed_at'], name='cr_cupon_redeemed_idx'),
            models.Index(fields=['phone_number'], name='cr_phone_num_idx'),
            models.Index(fields=['redeemed_at'], name='cr_redeemed_idx'),
            models.Index(fields=['phone_key'], name='cr_phone_key_idx'),
        ]

    def __str__(self):
        return f'{self.cupon.name} -> {self.customer.username} ({self.redeemed_at:%Y-%m-%d %H:%M})'

    @property
    def duration_text(self):
        qty = self.duration_quantity
        if self.duration_unit == Cupon.DURATION_UNIT_DAY:
            unit = 'día' if qty == 1 else 'días'
        elif self.duration_unit == Cupon.DURATION_UNIT_WEEK:
            unit = 'semana' if qty == 1 else 'semanas'
        elif self.duration_unit == Cupon.DURATION_UNIT_YEAR:
            unit = 'año' if qty == 1 else 'años'
        else:
            unit = 'mes' if qty == 1 else 'meses'
        return f"{qty} {unit}"
