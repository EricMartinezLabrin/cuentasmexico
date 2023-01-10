from adm.models import Business, Service, Account, Credits
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
        user_id = request.user.id
        credits = 0
        try:
            credits_query = Credits.objects.filter(customer=user_id).values('customer').annotate(suma=Sum('credits'))
            for q in credits_query:
                credits = q['suma']
                break
        except Credits.DoesNotExist:
            credits = 0
        
        return credits