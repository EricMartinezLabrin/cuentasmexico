from django.contrib import admin
from .models import Bank, PaymentMethod, Status, UserDetail, Account, Sale, Supplier, Business

# Register your models here.
admin.site.register(Bank)
admin.site.register(PaymentMethod)
admin.site.register(Status)
admin.site.register(UserDetail)
admin.site.register(Supplier)
admin.site.register(Account)
admin.site.register(Sale)
admin.site.register(Business)