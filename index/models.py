from django.db import models
from adm.models import Service
from django.contrib.auth.models import User

class IndexCart(models.Model):
    # Estados de pago para pagos diferidos (OXXO, transferencia)
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('awaiting_payment', 'Esperando pago'),
        ('processing', 'Procesando'),
        ('approved', 'Aprobado'),
        ('cancelled', 'Cancelado'),
        ('expired', 'Expirado'),
    ]

    payment_id = models.BigIntegerField(blank=True, null=True)
    date_created = models.DateTimeField(blank=True, null=True)
    date_approved = models.DateTimeField(blank=True, null=True)
    date_last_updated = models.DateTimeField(blank=True, null=True)
    money_release_date = models.DateTimeField(blank=True, null=True)
    payment_type_id = models.CharField(max_length=50, blank=True, null=True)
    status_detail = models.CharField(max_length=50, blank=True, null=True)
    currency_id = models.CharField(max_length=50, blank=True, null=True)
    description = models.CharField(max_length=50, blank=True, null=True)
    transaction_amount = models.IntegerField(blank=True, null=True)
    transaction_amount_refunded = models.IntegerField(blank=True, null=True)
    coupon_amount = models.IntegerField(blank=True, null=True)
    customer = models.ForeignKey(User, models.DO_NOTHING)
    # Campos para pagos diferidos (OXXO, transferencia bancaria)
    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='pending',
        blank=True,
        null=True
    )
    stripe_session_id = models.CharField(max_length=255, blank=True, null=True)
    payment_method_type = models.CharField(max_length=50, blank=True, null=True)  # card, oxxo, customer_balance
    hosted_voucher_url = models.URLField(max_length=500, blank=True, null=True)  # URL del voucher OXXO
    payment_expires_at = models.DateTimeField(blank=True, null=True)  # Fecha límite de pago

    class Meta:
        managed = True
        db_table = 'index_cart'


class IndexCartdetail(models.Model):
    long = models.IntegerField()
    quantity = models.IntegerField()
    price = models.IntegerField()
    cart = models.ForeignKey(IndexCart, models.DO_NOTHING)
    service = models.ForeignKey(Service, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'index_cartdetail'