from adm.models import Business, Service, Account

class BusinessInfo():
    
    def data():
        return Business.objects.get(pk=1)

    def cart_data():
        pass
    def count_sales(service_id):
        service = Service.objects.get(pk=service_id)
        accounts = Account.objects.filter(account_name=service).count()
        return accounts