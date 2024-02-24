from django.db import models
from adm.models import Service
from django.contrib.auth.models import User

class IndexCart(models.Model):
    payment_id = models.IntegerField(blank=True, null=True)
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

    class Meta:
        managed = False
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