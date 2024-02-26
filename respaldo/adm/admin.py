from django.contrib import admin
from .models import Bank, PaymentMethod, Status, UserDetail, Account, Sale, Supplier, Business, Level, Credits

class ParteAdmin(admin.ModelAdmin):
    # con esto muestras los campos que deses al mostrar la lista en admin
    # list_display=['user']
    # con esto añades un campo de texto que te permite realizar la busqueda, puedes añadir mas de un atributo por el cual se filtrará
    search_fields = ['user__username']
    # con esto añadiras una lista desplegable con la que podras filtrar (activo es un atributo booleano)
    list_filter = ['level']
	
class SearchAccount(admin.ModelAdmin):
    search_fields = ['email']
    list_filter = ['status','account_name_id']

# Register your models here.
admin.site.register(Bank)
admin.site.register(PaymentMethod)
admin.site.register(Status)
admin.site.register(UserDetail,ParteAdmin)
admin.site.register(Supplier)
admin.site.register(Account, SearchAccount)
admin.site.register(Sale)
admin.site.register(Business)
admin.site.register(Level)
admin.site.register(Credits)

