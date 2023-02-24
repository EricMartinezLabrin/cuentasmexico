# Django
from django.db.models import Sum, Count
from django.contrib.auth.models import User
from adm.models import UserDetail, Account, Service
from django.utils import timezone
# Python
from datetime import datetime, timedelta
import pandas as pd
from calendar import monthrange
# Local
from adm.models import Sale


class Dashboard():

    def sales_per_country_day():
        today = timezone.now()
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
        month = timezone.now().month
        year = timezone.now().year
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

        start = '2022-12-01 00:00:00'
        end = '2022-12-30 23:59:59'
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
