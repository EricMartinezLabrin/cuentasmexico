#Django
from django.db.models import Sum
#Python
from datetime import datetime,timedelta
#Local
from adm.models import Sale

class Dashboard():

    def sales_per_country():
        today = datetime.now()-timedelta(days=1)
        sales = Sale.objects.filter(created_at__range=(str(today.date())+' 00:00:00', str(today.date())+' 23:59:59'))
        sales_country = {}

        for s in sales:
            country = s.customer.userdetail.country
            if country in sales_country:
                sales_country[country] += s.payment_amount
            else:
                sales_country[country] = s.payment_amount

        # return sales.aggregate(Total=Sum('payment_amount'))
        return sales_country