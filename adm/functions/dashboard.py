# Django
from django.db.models import Sum, Count
from django.contrib.auth.models import User
from adm.models import UserDetail, Account, Service
from django.utils import timezone
# Python
from datetime import datetime, timedelta
from calendar import monthrange,month_name
# Local
from adm.models import Sale
from dateutil.relativedelta import relativedelta
import locale
locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8') 



class Dashboard():

    def sales_per_country_day():
        today = datetime.now()
        sales_country = {}
        countries = Sale.objects.values('customer__userdetail__country').order_by(
            'customer__userdetail__country').distinct()
        for country in countries:
            for key, value in country.items():
                sales = Sale.objects.filter(created_at__range=(str(today.date(
                ))+' 00:00:00', str(today.date())+' 23:59:59'), customer__userdetail__country=value)
                if not value:
                    continue
                sales_country[value] = sales.aggregate(Sum('payment_amount'))

        return sales_country

    def sales_per_country_month():
        month = datetime.now().month
        year = datetime.now().year
        last_day = monthrange(year, month)[1]
        start = f'{year}-{month}-01 00:00:00'
        end = f'{year}-{month}-{last_day} 23:59:59'

        sales_country = {}
        countries = Sale.objects.values('customer__userdetail__country').order_by(
            'customer__userdetail__country').distinct()
        for country in countries:
            for key, value in country.items():
                sales = Sale.objects.filter(created_at__range=(
                    start, end), customer__userdetail__country=value)
                if not value:
                    continue
                sales_country[value] = sales.aggregate(Sum('payment_amount'))
        return sales_country

    def sales_per_account():

        month = datetime.now().month
        year = datetime.now().year
        last_day = monthrange(year, month)[1]
        start = f'{year}-{month}-01 00:00:00'
        end = f'{year}-{month}-{last_day} 23:59:59'
        acc_name = []
        acc_total = []
        acc = Sale.objects.filter(created_at__range=(start, end)).exclude(payment_amount=0).values(
            'account__account_name').order_by('account__account_name').distinct()
        for a in acc:
            for key, value in a.items():
                sales = Sale.objects.filter(created_at__range=(
                    start, end), account__account_name=value)
                subtotal = sales.aggregate(Count('payment_amount'))
                acc_name.append(Service.objects.get(pk=value).description)
                for key, value in subtotal.items():
                    if value == None:
                        value = 0
                    acc_total.append(value)
        return acc_name, acc_total

    def new_formated_date(date, months):
        date = date - relativedelta(months=months)
        return date.strftime('%Y-%m')

    def last_year_sales_new_user():
        last_year_monts = []
        date = datetime.now()
        for i in range(13):
            sales_new_customer = Sale.objects.filter(customer__date_joined__startswith=Dashboard.new_formated_date(date,i), payment_amount__gt=0,customer__userdetail__lada=52)
            total = sales_new_customer.aggregate(Sum('payment_amount'))
            new_date = datetime.strptime(Dashboard.new_formated_date(date, i), "%Y-%m")
            month = new_date.month 
            last_year_monts.append({'date':month_name[month],'sales':total['payment_amount__sum'] , 'new_users': sales_new_customer.count()})

        return last_year_monts
    
    def sales_per_day_new_user(date):
        date = date.strftime('%Y-%m-%d')
        sales = Sale.objects.filter(customer__date_joined__startswith=date, payment_amount__gt=0,customer__userdetail__lada=52)
        total = sales.aggregate(Sum('payment_amount'))
        if total['payment_amount__sum'] == None:
            total['payment_amount__sum'] = 0
        return {date:{'sales':total['payment_amount__sum'] , 'new_users': sales.count()}}

