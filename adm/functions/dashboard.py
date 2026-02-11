# Django
from django.db.models import Sum, Count
from django.contrib.auth.models import User
from adm.models import UserDetail, Account, Service, PageVisit
from django.utils import timezone
# Python
from datetime import datetime, timedelta
from calendar import monthrange,month_name
# Local
from adm.models import Sale
from dateutil.relativedelta import relativedelta



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

    # ========== NUEVAS FUNCIONES PARA ESTADÍSTICAS WEB ==========

    def page_visits_by_page():
        """
        Contador de visitas por página (total acumulado)
        Retorna un diccionario con el nombre de la página y el total de visitas
        Incluye clics en servicios categorizados con el nombre del servicio
        """
        visits = PageVisit.objects.values('page').annotate(
            total=Count('id')
        ).order_by('-total')

        result = {}
        for visit in visits:
            page_name = dict(PageVisit.PAGE_CHOICES).get(visit['page'], visit['page'])
            result[page_name] = visit['total']
        
        # Agregar clics en servicios como páginas individuales
        service_clicks = PageVisit.objects.filter(
            page='service',
            service__isnull=False
        ).values('service__description').annotate(
            total=Count('id')
        ).order_by('-total')
        
        for click in service_clicks:
            service_name = click['service__description']
            result[service_name] = click['total']

        return result

    def page_visits_today():
        """
        Visitas de hoy por página
        Incluye clics en servicios categorizados con el nombre del servicio
        """
        today = timezone.now().date()
        start = timezone.make_aware(datetime.combine(today, datetime.min.time()))
        end = timezone.make_aware(datetime.combine(today, datetime.max.time()))

        visits = PageVisit.objects.filter(
            visited_at__range=(start, end)
        ).values('page').annotate(
            total=Count('id')
        ).order_by('-total')

        result = {}
        for visit in visits:
            page_name = dict(PageVisit.PAGE_CHOICES).get(visit['page'], visit['page'])
            result[page_name] = visit['total']
        
        # Agregar clics en servicios de hoy
        service_clicks = PageVisit.objects.filter(
            visited_at__range=(start, end),
            page='service',
            service__isnull=False
        ).values('service__description').annotate(
            total=Count('id')
        ).order_by('-total')
        
        for click in service_clicks:
            service_name = click['service__description']
            result[service_name] = click['total']

        return result

    def page_visits_last_7_days():
        """
        Visitas de los últimos 7 días por página
        Incluye clics en servicios categorizados con el nombre del servicio
        """
        today = timezone.now()
        seven_days_ago = today - timedelta(days=7)

        visits = PageVisit.objects.filter(
            visited_at__gte=seven_days_ago
        ).values('page').annotate(
            total=Count('id')
        ).order_by('-total')

        result = {}
        for visit in visits:
            page_name = dict(PageVisit.PAGE_CHOICES).get(visit['page'], visit['page'])
            result[page_name] = visit['total']
        
        # Agregar clics en servicios de los últimos 7 días
        service_clicks = PageVisit.objects.filter(
            visited_at__gte=seven_days_ago,
            page='service',
            service__isnull=False
        ).values('service__description').annotate(
            total=Count('id')
        ).order_by('-total')
        
        for click in service_clicks:
            service_name = click['service__description']
            result[service_name] = click['total']

        return result

    def unique_visitors_today():
        """
        Visitantes únicos de hoy (por IP y session)
        """
        today = timezone.now().date()
        start = timezone.make_aware(datetime.combine(today, datetime.min.time()))
        end = timezone.make_aware(datetime.combine(today, datetime.max.time()))

        unique_ips = PageVisit.objects.filter(
            visited_at__range=(start, end)
        ).values('ip_address').distinct().count()

        unique_sessions = PageVisit.objects.filter(
            visited_at__range=(start, end)
        ).values('session_key').distinct().count()

        return {
            'unique_ips': unique_ips,
            'unique_sessions': unique_sessions
        }

    # ========== ESTADÍSTICAS DE VENTAS WEB ==========

    def web_sales_today():
        """
        Ventas realizadas SOLO por la web HOY (MercadoPago, Stripe, PayPal)
        Excluye ventas manuales del admin
        """
        from django.db.models import Q

        today = timezone.now().date()
        start = timezone.make_aware(datetime.combine(today, datetime.min.time()))
        end = timezone.make_aware(datetime.combine(today, datetime.max.time()))

        # Solo contar ventas con pasarelas de pago (MercadoPago, Stripe, PayPal)
        web_sales = Sale.objects.filter(
            created_at__range=(start, end)
        ).filter(
            Q(payment_method__description__icontains='MercadoPago') |
            Q(payment_method__description__icontains='Mercado Pago') |
            Q(payment_method__description__icontains='Stripe') |
            Q(payment_method__description__icontains='PayPal')
        )

        total = web_sales.aggregate(Sum('payment_amount'))
        count = web_sales.count()

        return {
            'total': total['payment_amount__sum'] or 0,
            'count': count
        }

    def web_sales_weekly():
        """
        Ventas por la web esta semana (solo pasarelas de pago)
        """
        from django.db.models import Q

        today = timezone.now()
        week_start = today - timedelta(days=today.weekday())
        week_start = timezone.make_aware(datetime.combine(week_start.date(), datetime.min.time()))

        # Solo contar ventas con pasarelas de pago
        web_sales = Sale.objects.filter(
            created_at__gte=week_start
        ).filter(
            Q(payment_method__description__icontains='MercadoPago') |
            Q(payment_method__description__icontains='Mercado Pago') |
            Q(payment_method__description__icontains='Stripe') |
            Q(payment_method__description__icontains='PayPal')
        )

        total = web_sales.aggregate(Sum('payment_amount'))
        count = web_sales.count()

        return {
            'total': total['payment_amount__sum'] or 0,
            'count': count
        }

    def web_sales_monthly():
        """
        Ventas por la web este mes (solo pasarelas de pago)
        """
        from django.db.models import Q

        month = timezone.now().month
        year = timezone.now().year
        last_day = monthrange(year, month)[1]

        start = timezone.make_aware(datetime(year, month, 1, 0, 0, 0))
        end = timezone.make_aware(datetime(year, month, last_day, 23, 59, 59))

        # Solo contar ventas con pasarelas de pago
        web_sales = Sale.objects.filter(
            created_at__range=(start, end)
        ).filter(
            Q(payment_method__description__icontains='MercadoPago') |
            Q(payment_method__description__icontains='Mercado Pago') |
            Q(payment_method__description__icontains='Stripe') |
            Q(payment_method__description__icontains='PayPal')
        )

        total = web_sales.aggregate(Sum('payment_amount'))
        count = web_sales.count()

        return {
            'total': total['payment_amount__sum'] or 0,
            'count': count
        }

    def web_sales_yearly():
        """
        Ventas por la web este año (solo pasarelas de pago)
        """
        from django.db.models import Q

        year = timezone.now().year

        start = timezone.make_aware(datetime(year, 1, 1, 0, 0, 0))
        end = timezone.make_aware(datetime(year, 12, 31, 23, 59, 59))

        # Solo contar ventas con pasarelas de pago
        web_sales = Sale.objects.filter(
            created_at__range=(start, end)
        ).filter(
            Q(payment_method__description__icontains='MercadoPago') |
            Q(payment_method__description__icontains='Mercado Pago') |
            Q(payment_method__description__icontains='Stripe') |
            Q(payment_method__description__icontains='PayPal')
        )

        total = web_sales.aggregate(Sum('payment_amount'))
        count = web_sales.count()

        return {
            'total': total['payment_amount__sum'] or 0,
            'count': count
        }

    def web_sales_last_12_months():
        """
        Ventas por la web últimos 12 meses (para gráfico)
        Solo incluye ventas con pasarelas de pago (MercadoPago, Stripe, PayPal)
        """
        from django.db.models import Q

        result = []
        date = timezone.now()

        for i in range(12):
            month_date = date - relativedelta(months=i)
            year = month_date.year
            month = month_date.month
            last_day = monthrange(year, month)[1]

            start = timezone.make_aware(datetime(year, month, 1, 0, 0, 0))
            end = timezone.make_aware(datetime(year, month, last_day, 23, 59, 59))

            # Solo contar ventas con pasarelas de pago usando Q para OR
            web_sales = Sale.objects.filter(
                created_at__range=(start, end)
            ).filter(
                Q(payment_method__description__icontains='MercadoPago') |
                Q(payment_method__description__icontains='Mercado Pago') |
                Q(payment_method__description__icontains='Stripe') |
                Q(payment_method__description__icontains='PayPal')
            )

            total = web_sales.aggregate(Sum('payment_amount'))

            result.append({
                'month': month_name[month],
                'year': year,
                'total': total['payment_amount__sum'] or 0,
                'count': web_sales.count()
            })

        return list(reversed(result))

    def page_visits_last_30_days_chart():
        """
        Visitas por día de los últimos 30 días (para gráfico de líneas)
        """
        result = []
        today = timezone.now()

        for i in range(30):
            day = today - timedelta(days=i)
            day_start = timezone.make_aware(datetime.combine(day.date(), datetime.min.time()))
            day_end = timezone.make_aware(datetime.combine(day.date(), datetime.max.time()))

            visits = PageVisit.objects.filter(
                visited_at__range=(day_start, day_end)
            ).count()

            result.append({
                'date': day.strftime('%Y-%m-%d'),
                'visits': visits
            })

        return list(reversed(result))

    # ========== FUNCIONES DE DETALLE PARA ESTADÍSTICAS WEB ==========

    def get_web_sales_today_detail():
        """
        Detalle completo de las ventas web de HOY
        Retorna lista de ventas individuales con todos sus datos
        """
        from django.db.models import Q

        today = timezone.now().date()
        start = timezone.make_aware(datetime.combine(today, datetime.min.time()))
        end = timezone.make_aware(datetime.combine(today, datetime.max.time()))

        # Usar el mismo filtro que las funciones de resumen para consistencia
        web_sales = Sale.objects.filter(
            created_at__range=(start, end)
        ).filter(
            Q(payment_method__description__icontains='MercadoPago') |
            Q(payment_method__description__icontains='Mercado Pago') |
            Q(payment_method__description__icontains='Stripe') |
            Q(payment_method__description__icontains='PayPal')
        ).select_related(
            'customer', 'customer__userdetail', 'account',
            'account__account_name', 'payment_method'
        ).order_by('-created_at')

        return web_sales

    def get_web_sales_weekly_detail():
        """
        Detalle completo de las ventas web de ESTA SEMANA
        """
        from django.db.models import Q

        today = timezone.now()
        week_start = today - timedelta(days=today.weekday())
        week_start = timezone.make_aware(datetime.combine(week_start.date(), datetime.min.time()))

        # Usar el mismo filtro que las funciones de resumen para consistencia
        web_sales = Sale.objects.filter(
            created_at__gte=week_start
        ).filter(
            Q(payment_method__description__icontains='MercadoPago') |
            Q(payment_method__description__icontains='Mercado Pago') |
            Q(payment_method__description__icontains='Stripe') |
            Q(payment_method__description__icontains='PayPal')
        ).select_related(
            'customer', 'customer__userdetail', 'account',
            'account__account_name', 'payment_method'
        ).order_by('-created_at')

        return web_sales

    def get_web_sales_monthly_detail():
        """
        Detalle completo de las ventas web de ESTE MES
        """
        from django.db.models import Q

        month = timezone.now().month
        year = timezone.now().year
        last_day = monthrange(year, month)[1]

        start = timezone.make_aware(datetime(year, month, 1, 0, 0, 0))
        end = timezone.make_aware(datetime(year, month, last_day, 23, 59, 59))

        # Usar el mismo filtro que las funciones de resumen para consistencia
        web_sales = Sale.objects.filter(
            created_at__range=(start, end)
        ).filter(
            Q(payment_method__description__icontains='MercadoPago') |
            Q(payment_method__description__icontains='Mercado Pago') |
            Q(payment_method__description__icontains='Stripe') |
            Q(payment_method__description__icontains='PayPal')
        ).select_related(
            'customer', 'customer__userdetail', 'account',
            'account__account_name', 'payment_method'
        ).order_by('-created_at')

        return web_sales

    def get_web_sales_yearly_detail():
        """
        Detalle completo de las ventas web de ESTE AÑO
        """
        from django.db.models import Q

        year = timezone.now().year

        start = timezone.make_aware(datetime(year, 1, 1, 0, 0, 0))
        end = timezone.make_aware(datetime(year, 12, 31, 23, 59, 59))

        # Usar el mismo filtro que las funciones de resumen para consistencia
        web_sales = Sale.objects.filter(
            created_at__range=(start, end)
        ).filter(
            Q(payment_method__description__icontains='MercadoPago') |
            Q(payment_method__description__icontains='Mercado Pago') |
            Q(payment_method__description__icontains='Stripe') |
            Q(payment_method__description__icontains='PayPal')
        ).select_related(
            'customer', 'customer__userdetail', 'account',
            'account__account_name', 'payment_method'
        ).order_by('-created_at')

        return web_sales

    # ========== NUEVAS FUNCIONES PARA FILTROS POR PERÍODO ==========

    @staticmethod
    def get_date_range(period, custom_start=None, custom_end=None):
        """
        Retorna el rango de fechas según el período seleccionado
        """
        today = timezone.now().date()
        
        if period == 'CUSTOM' and custom_start and custom_end:
            # Período personalizado
            try:
                start_date = datetime.strptime(custom_start, '%Y-%m-%d').date()
                end_date = datetime.strptime(custom_end, '%Y-%m-%d').date()
                start = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
                end = timezone.make_aware(datetime.combine(end_date, datetime.max.time()))
                return start, end
            except ValueError:
                # Si hay error en el formato, usar hoy por defecto
                pass
        
        if period == 'HOY':
            start = timezone.make_aware(datetime.combine(today, datetime.min.time()))
            end = timezone.make_aware(datetime.combine(today, datetime.max.time()))
            
        elif period == 'AYER':
            yesterday = today - timedelta(days=1)
            start = timezone.make_aware(datetime.combine(yesterday, datetime.min.time()))
            end = timezone.make_aware(datetime.combine(yesterday, datetime.max.time()))
            
        elif period == 'ESTA_SEMANA':
            week_start = today - timedelta(days=today.weekday())
            start = timezone.make_aware(datetime.combine(week_start, datetime.min.time()))
            end = timezone.make_aware(datetime.combine(today, datetime.max.time()))
            
        elif period == 'ESTE_MES':
            month = today.month
            year = today.year
            last_day = monthrange(year, month)[1]
            start = timezone.make_aware(datetime(year, month, 1, 0, 0, 0))
            end = timezone.make_aware(datetime(year, month, last_day, 23, 59, 59))
            
        elif period == 'ULTIMOS_7_DIAS':
            start_date = today - timedelta(days=7)
            start = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
            end = timezone.make_aware(datetime.combine(today, datetime.max.time()))
            
        elif period == 'ULTIMOS_30_DIAS':
            start_date = today - timedelta(days=30)
            start = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
            end = timezone.make_aware(datetime.combine(today, datetime.max.time()))
            
        else:
            # Por defecto, hoy
            start = timezone.make_aware(datetime.combine(today, datetime.min.time()))
            end = timezone.make_aware(datetime.combine(today, datetime.max.time()))
            
        return start, end

    def sales_by_period(period='HOY', custom_start=None, custom_end=None):
        """
        Ventas totales por período
        """
        from django.db.models import Q
        
        start, end = Dashboard.get_date_range(period, custom_start, custom_end)
        
        # Ventas totales (todas)
        total_sales = Sale.objects.filter(
            created_at__range=(start, end)
        ).aggregate(
            total_amount=Sum('payment_amount'),
            total_count=Count('id')
        )
        
        # Ventas web (solo pasarelas de pago)
        web_sales = Sale.objects.filter(
            created_at__range=(start, end)
        ).filter(
            Q(payment_method__description__icontains='MercadoPago') |
            Q(payment_method__description__icontains='Mercado Pago') |
            Q(payment_method__description__icontains='Stripe') |
            Q(payment_method__description__icontains='PayPal')
        ).aggregate(
            web_amount=Sum('payment_amount'),
            web_count=Count('id')
        )
        
        # Ventas manuales (admin)
        manual_sales = Sale.objects.filter(
            created_at__range=(start, end)
        ).exclude(
            Q(payment_method__description__icontains='MercadoPago') |
            Q(payment_method__description__icontains='Mercado Pago') |
            Q(payment_method__description__icontains='Stripe') |
            Q(payment_method__description__icontains='PayPal')
        ).aggregate(
            manual_amount=Sum('payment_amount'),
            manual_count=Count('id')
        )
        
        return {
            'period': period,
            'total': {
                'amount': total_sales['total_amount'] or 0,
                'count': total_sales['total_count'] or 0
            },
            'web': {
                'amount': web_sales['web_amount'] or 0,
                'count': web_sales['web_count'] or 0
            },
            'manual': {
                'amount': manual_sales['manual_amount'] or 0,
                'count': manual_sales['manual_count'] or 0
            }
        }

    def sales_by_country_period(period='HOY', custom_start=None, custom_end=None):
        """
        Ventas por país para un período específico
        """
        start, end = Dashboard.get_date_range(period, custom_start, custom_end)
        
        sales_country = {}
        countries = Sale.objects.filter(
            created_at__range=(start, end)
        ).values('customer__userdetail__country').order_by(
            'customer__userdetail__country'
        ).distinct()
        
        for country in countries:
            for key, value in country.items():
                if not value:
                    continue
                    
                sales = Sale.objects.filter(
                    created_at__range=(start, end),
                    customer__userdetail__country=value
                )
                
                total = sales.aggregate(Sum('payment_amount'))
                count = sales.count()
                
                sales_country[value] = {
                    'amount': total['payment_amount__sum'] or 0,
                    'count': count
                }
        
        return sales_country

    def sales_by_service_period(period='HOY', custom_start=None, custom_end=None):
        """
        Ventas por servicio para un período específico
        """
        start, end = Dashboard.get_date_range(period, custom_start, custom_end)
        
        services_data = {}
        services = Sale.objects.filter(
            created_at__range=(start, end)
        ).values('account__account_name__description').order_by(
            'account__account_name__description'
        ).distinct()
        
        for service in services:
            for key, value in service.items():
                if not value:
                    continue
                    
                sales = Sale.objects.filter(
                    created_at__range=(start, end),
                    account__account_name__description=value
                )
                
                total = sales.aggregate(Sum('payment_amount'))
                count = sales.count()
                
                services_data[value] = {
                    'amount': total['payment_amount__sum'] or 0,
                    'count': count
                }
        
        return services_data

    def new_users_by_period(period='HOY', custom_start=None, custom_end=None):
        """
        Nuevos usuarios por período
        """
        start, end = Dashboard.get_date_range(period, custom_start, custom_end)
        
        new_users = User.objects.filter(
            date_joined__range=(start, end)
        ).count()
        
        # Nuevos usuarios con ventas (México)
        new_users_with_sales = Sale.objects.filter(
            created_at__range=(start, end),
            customer__userdetail__lada=52,
            payment_amount__gt=0
        ).values('customer').distinct().count()
        
        return {
            'total_new_users': new_users,
            'new_users_with_sales_mx': new_users_with_sales
        }

    def page_visits_by_period(period='HOY', custom_start=None, custom_end=None):
        """
        Visitas a páginas por período
        """
        start, end = Dashboard.get_date_range(period, custom_start, custom_end)
        
        visits = PageVisit.objects.filter(
            visited_at__range=(start, end)
        ).values('page').annotate(
            total=Count('id')
        ).order_by('-total')
        
        result = {}
        for visit in visits:
            page_name = dict(PageVisit.PAGE_CHOICES).get(visit['page'], visit['page'])
            result[page_name] = visit['total']
        
        # Agregar clics en servicios
        service_clicks = PageVisit.objects.filter(
            visited_at__range=(start, end),
            page='service',
            service__isnull=False
        ).values('service__description').annotate(
            total=Count('id')
        ).order_by('-total')
        
        for click in service_clicks:
            service_name = click['service__description']
            result[service_name] = click['total']
        
        # Visitantes únicos
        unique_ips = PageVisit.objects.filter(
            visited_at__range=(start, end)
        ).values('ip_address').distinct().count()
        
        unique_sessions = PageVisit.objects.filter(
            visited_at__range=(start, end)
        ).values('session_key').distinct().count()
        
        return {
            'visits_by_page': result,
            'unique_ips': unique_ips,
            'unique_sessions': unique_sessions,
            'total_visits': sum(result.values())
        }

    def sales_trend_chart(period='ULTIMOS_30_DIAS', custom_start=None, custom_end=None):
        """
        Gráfico de tendencia de ventas para el período seleccionado
        """
        start, end = Dashboard.get_date_range(period, custom_start, custom_end)
        
        # Determinar granularidad basada en el período
        if period in ['HOY', 'AYER']:
            # Por hora
            granularity = 'hour'
        elif period in ['ESTA_SEMANA', 'ULTIMOS_7_DIAS']:
            # Por día
            granularity = 'day'
        else:
            # Por día para períodos más largos
            granularity = 'day'
        
        result = []
        
        if granularity == 'hour':
            # Agrupar por hora
            current = start
            while current <= end:
                hour_start = current
                hour_end = current + timedelta(hours=1)
                
                sales = Sale.objects.filter(
                    created_at__range=(hour_start, hour_end)
                ).aggregate(
                    total=Sum('payment_amount'),
                    count=Count('id')
                )
                
                result.append({
                    'label': hour_start.strftime('%H:00'),
                    'date': hour_start.strftime('%Y-%m-%d %H:00:00'),
                    'total': sales['total'] or 0,
                    'count': sales['count'] or 0
                })
                
                current = hour_end
                
        else:
            # Agrupar por día
            current_date = start.date()
            end_date = end.date()
            
            while current_date <= end_date:
                day_start = timezone.make_aware(datetime.combine(current_date, datetime.min.time()))
                day_end = timezone.make_aware(datetime.combine(current_date, datetime.max.time()))
                
                sales = Sale.objects.filter(
                    created_at__range=(day_start, day_end)
                ).aggregate(
                    total=Sum('payment_amount'),
                    count=Count('id')
                )
                
                result.append({
                    'label': current_date.strftime('%d/%m'),
                    'date': current_date.strftime('%Y-%m-%d'),
                    'total': sales['total'] or 0,
                    'count': sales['count'] or 0
                })
                
                current_date += timedelta(days=1)
        
        return result

    def top_services_by_period(period='HOY', limit=5, custom_start=None, custom_end=None):
        """
        Top servicios más vendidos por período
        """
        start, end = Dashboard.get_date_range(period, custom_start, custom_end)
        
        top_services = Sale.objects.filter(
            created_at__range=(start, end)
        ).values(
            'account__account_name__description'
        ).annotate(
            total_amount=Sum('payment_amount'),
            total_count=Count('id')
        ).order_by('-total_amount')[:limit]
        
        result = []
        for service in top_services:
            result.append({
                'service': service['account__account_name__description'],
                'amount': service['total_amount'] or 0,
                'count': service['total_count'] or 0
            })
        
        return result

    def top_countries_by_period(period='HOY', limit=5, custom_start=None, custom_end=None):
        """
        Top países por ventas en el período
        """
        start, end = Dashboard.get_date_range(period, custom_start, custom_end)
        
        top_countries = Sale.objects.filter(
            created_at__range=(start, end)
        ).values(
            'customer__userdetail__country'
        ).annotate(
            total_amount=Sum('payment_amount'),
            total_count=Count('id')
        ).order_by('-total_amount')[:limit]
        
        result = []
        for country in top_countries:
            country_name = country['customer__userdetail__country'] or 'Desconocido'
            result.append({
                'country': country_name,
                'amount': country['total_amount'] or 0,
                'count': country['total_count'] or 0
            })
        
        return result

    def conversion_rate_by_period(period='HOY', custom_start=None, custom_end=None):
        """
        Tasa de conversión (visitas vs ventas) por período
        """
        start, end = Dashboard.get_date_range(period, custom_start, custom_end)
        
        # Total de visitas
        total_visits = PageVisit.objects.filter(
            visited_at__range=(start, end)
        ).count()
        
        # Total de ventas
        total_sales = Sale.objects.filter(
            created_at__range=(start, end)
        ).count()
        
        # Calcular tasa de conversión
        if total_visits > 0:
            conversion_rate = (total_sales / total_visits) * 100
        else:
            conversion_rate = 0
        
        return {
            'total_visits': total_visits,
            'total_sales': total_sales,
            'conversion_rate': round(conversion_rate, 2)
        }

    def average_ticket_by_period(period='HOY', custom_start=None, custom_end=None):
        """
        Ticket promedio por período
        """
        start, end = Dashboard.get_date_range(period, custom_start, custom_end)
        
        sales_data = Sale.objects.filter(
            created_at__range=(start, end)
        ).aggregate(
            total_amount=Sum('payment_amount'),
            total_count=Count('id')
        )
        
        total_amount = sales_data['total_amount'] or 0
        total_count = sales_data['total_count'] or 0
        
        if total_count > 0:
            average_ticket = total_amount / total_count
        else:
            average_ticket = 0
        
        return {
            'average_ticket': round(average_ticket, 2),
            'total_amount': total_amount,
            'total_count': total_count
        }



