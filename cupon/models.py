from django.db import models
from adm.models import Sale
from django.contrib.auth.models import User

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

class Cupon(models.Model):
    name = models.CharField(max_length=30, unique=True)
    status = models.BooleanField(default=True)
    long = models.IntegerField()
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
