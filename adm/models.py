#python


#django
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator

class Business(models.Model):
    name = models.CharField(max_length=50)
    email = models.EmailField(max_length=30)
    url = models.CharField(max_length=50)
    phoneNumberRegex = RegexValidator(regex = r"^\+?1?\d{8,15}$")
    phone_number = models.CharField(validators = [phoneNumberRegex],max_length=16,null=False, blank=False)
    mp_customer_key = models.CharField(max_length=100, null=True, blank=True)
    mp_secret_key = models.CharField(max_length=100, null=True, blank=True)
    logo = models.FileField(upload_to="settings/", null=True, blank=True)

    def __str__(self):
        return self.name

class Service(models.Model):
    description = models.CharField(max_length=40)
    perfil_quantity = models.IntegerField()
    status = models.BooleanField(default=True)
    logo = models.FileField(upload_to="settings/", null=True, blank=True)
    old_id = models.IntegerField(blank=True,null=True)

    def __str__(self):
        return self.description

class Bank(models.Model):
    business = models.ForeignKey(Business, on_delete=models.DO_NOTHING)
    bank_name = models.CharField(max_length=30, null=False)
    headline = models.CharField(max_length=30, null=False)
    card_number = models.CharField(max_length=16,null=False)
    clabe = models.CharField(max_length=18,null=False)
    logo = models.FileField(upload_to="bank/", null=True, blank=True)
    status = models.BooleanField(default=True)

    def __str__(self):
        return str(self.card_number) + " " + self.headline

class PaymentMethod(models.Model):
    description = models.CharField(max_length=40, null=False)

    def __str__(self):
        return self.description

class Status(models.Model):
    description = models.CharField(max_length=40, null=False)

    def __str__(self):
        return self.description

class UserDetail(models.Model):
    business = models.ForeignKey(Business, on_delete=models.DO_NOTHING)
    phoneNumberRegex = RegexValidator(regex = r"^\+?1?\d{8,15}$")
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone_number = models.CharField(validators = [phoneNumberRegex],max_length=16,null=False)
    lada = models.IntegerField(null=False)
    country = models.CharField(max_length=40, null=False)
    picture = models.FileField(upload_to="users/", null=True, blank=True)
    reference = models.IntegerField(null=True,blank=True)
    reference_used = models.BooleanField(default=False)
    free_days = models.IntegerField(default=0)

    def __str__(self):
        return self.user.username

class Supplier(models.Model):
    business = models.ForeignKey(Business, on_delete=models.DO_NOTHING)
    phoneNumberRegex = RegexValidator(regex = r"^\+?1?\d{8,15}$")
    name = models.CharField(max_length=50, null=False, blank=False)
    phone_number = models.CharField(validators = [phoneNumberRegex],max_length=16,null=False, blank=False)

    def __str__(self):
        return self.name
        
class Account(models.Model):
    business = models.ForeignKey(Business, on_delete=models.DO_NOTHING)
    supplier= models.ForeignKey(Supplier, on_delete=models.DO_NOTHING, default=1)
    status = models.BooleanField(default=True)
    customer = models.ForeignKey(User,null=True, blank=True,on_delete=models.CASCADE, related_name = 'adm_customer')
    created_by = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name = 'created_by')
    modified_by = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='modified_by')
    account_name = models.ForeignKey(Service, on_delete=models.DO_NOTHING)
    created_at = models.DateTimeField(auto_now=False, auto_now_add=True, null=False)
    expiration_date = models.DateTimeField(auto_now=False, auto_now_add=False, null=False)
    email = models.EmailField(max_length=50, null=False)
    password = models.CharField(max_length=50, null=False)
    pin = models.IntegerField(blank=True, null=True)
    comments = models.CharField(max_length=250, null=True, blank=True, default="")
    profile = models.IntegerField(null=True, blank=True, default=1)
    sent = models.BooleanField(null=True, blank=True,default=False)
    renovable = models.BooleanField(null=True, blank=True, default=False)
    

    def __str__(self):
        return self.account_name.description + "," + self.email

class Sale(models.Model):
    business = models.ForeignKey(Business, on_delete=models.DO_NOTHING)
    user_seller = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name="Worker")
    bank = models.ForeignKey(Bank,on_delete=models.DO_NOTHING,blank=True, null=True)
    customer = models.ForeignKey(User,on_delete=models.DO_NOTHING,related_name='Customer')
    account = models.ForeignKey(Account,on_delete=models.DO_NOTHING)
    status = models.BooleanField(default=True)
    payment_method = models.ForeignKey(PaymentMethod, on_delete=models.DO_NOTHING,blank=True,null=True)
    created_at = models.DateTimeField(auto_now=False, auto_now_add=True)
    expiration_date = models.DateTimeField(auto_now=False, auto_now_add=False)
    payment_amount = models.IntegerField(null=False)
    invoice = models.CharField(max_length=250, null=False)
    comment = models.CharField(max_length=255, blank=True, null=True)
    old_acc = models.IntegerField(null=True,blank=True)

    def __str__(self):
        return self.customer.userdetail.phone_number
