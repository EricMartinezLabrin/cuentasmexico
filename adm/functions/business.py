from adm.models import Business, Service, Account, Credits, UserDetail
from django.db.models import Sum

class BusinessInfo():
    
    def data():
        return Business.objects.get(pk=1)

    def cart_data():
        pass
    def count_sales(service_id):
        service = Service.objects.get(pk=service_id)
        accounts = Account.objects.filter(account_name=service).count()
        return accounts

    def credits(request):
        user = getattr(request, 'user', None)
        if not user or user.is_anonymous:
            return 0

        try:
            user_detail = user.userdetail
            if user_detail.associated_shop:
                credits_query = Credits.objects.filter(
                    shop=user_detail.associated_shop
                ).aggregate(suma=Sum('credits'))
                return credits_query['suma'] or 0
        except UserDetail.DoesNotExist:
            pass

        credits_query = Credits.objects.filter(customer=user).aggregate(suma=Sum('credits'))
        return credits_query['suma'] or 0
