from django.db import models
from django.contrib.auth.models import User
from adm.models import Service

# Create your models here.

class Cart(models.Model):
    payment_id = models.IntegerField(blank=True,null=True)
    date_created = models.DateTimeField(blank=True,null=True, auto_now=False, auto_now_add=False)
    date_approved = models.DateTimeField(blank=True,null=True, auto_now=False, auto_now_add=False)
    date_last_updated = models.DateTimeField(blank=True,null=True, auto_now=False, auto_now_add=False)
    money_release_date = models.DateTimeField(blank=True,null=True, auto_now=False, auto_now_add=False)
    payment_type_id = models.CharField(max_length=50,blank=True,null=True,)
    status_detail = models.CharField(max_length=50,blank=True,null=True,)
    currency_id = models.CharField(max_length=50,blank=True,null=True,)
    description = models.CharField(max_length=50,blank=True,null=True,)
    transaction_amount = models.IntegerField(blank=True,null=True)
    transaction_amount_refunded  = models.IntegerField(blank=True,null=True)
    coupon_amount  = models.IntegerField(blank=True,null=True)
    customer = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return f'Orden {self.payment_id}: {self.customer.username}'

class CartDetail(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE)
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    long = models.IntegerField()
    quantity = models.IntegerField()
    price = models.IntegerField()

    def __str__(self):
        return str(self.cart)