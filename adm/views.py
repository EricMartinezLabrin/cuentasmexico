# Django
import csv
import json
import base64
import re
from io import BytesIO
from django.shortcuts import render
from django.http import HttpResponse, HttpRequest
from django.core.files.base import ContentFile
from django.views.generic import DetailView, CreateView, UpdateView, TemplateView, ListView, DeleteView
from django.urls import reverse, reverse_lazy
from django.contrib.auth.decorators import permission_required, login_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.shortcuts import redirect
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.http import JsonResponse
from django.db.models import Sum, Prefetch, Case, When, IntegerField, Q, Count
from django.db.models import Max
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.db.models import DateTimeField, ExpressionWrapper, F
from calendar import monthrange
# Python
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from threading import Thread
import requests
import json
import logging
import sys
import os
import pyperclip as clipboard
from adm.functions.send_whatsapp_notification import Notification
from api.functions.notifications import send_push_notification
from django.db.models import DurationField
# import pandas as pd
# Local
from .models import (
    Business, PaymentMethod, Sale, UserDetail, Service, Account, Bank,
    Status, Supplier, Credits, Promocion, AccountChangeHistory,
    Affiliate, AffiliateCommission, AffiliateWithdrawal, AffiliateSettings, AffiliateSale, AISettings,
    MarketingCampaign, MarketingCampaignRecommendation, MarketingCampaignDelivery
)
from cupon.models import Cupon, CouponRedemption
from cupon.forms import CuponForm
from cupon.services import CouponRedeemError, normalize_code, validate_coupon_from_code
from .functions.alerts import Alerts
from .functions.forms import (
    AISettingsForm,
    AccountsForm,
    BankForm,
    PaymentMethodForm,
    ServicesForm,
    SettingsForm,
    UserDetailForm,
    UserForm,
    FilterAccountForm,
    StatusForm,
    SupplierForm,
    CustomerUpdateForm,
    UserMainForm,
)
from .functions.forms_marketing import MarketingCampaignForm
from .functions.permissions import UserAccessMixin
from .functions.country import Country
from .functions.active_inactive import Active_Inactive
from .functions.dashboard import Dashboard
from adm.functions.duplicated import NoDuplicate
from adm.functions.sales import Sales
from adm.functions.crm import CRMAnalytics
from CuentasMexico.ai import AIClient
from CuentasMexico.ai.config import get_active_provider, get_model_for_task, get_db_mcp_config
from CuentasMexico.ai.mcp_readonly_db import ReadOnlyDatabaseMCP
# from adm.functions.import_data import ImportData
from adm.db.constants import URL
import os
try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None

def is_ajax(request):
    return request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest'

def _send_notifications_background(sales_to_report, email, password, data_account, webhook_url):
    """
    Envía notificaciones en segundo plano sin bloquear la respuesta
    """
    try:
        # Pre-fetch todos los UserDetail
        customer_ids = [sale[0].customer.id for sale in sales_to_report if sale]
        user_details = {ud.user_id: ud for ud in UserDetail.objects.filter(user_id__in=customer_ids)}
        
        for customer in sales_to_report:
            try:
                sale_obj = customer[0]
                customer_detail = user_details.get(sale_obj.customer.id)
                if not customer_detail:
                    continue
                
                message = f'Le informamos que por su seguridad las claves de su cuenta {data_account.account_name} fueron cambiadas. A continuación le dejo sus nuevas claves:\n'
                message += f'Email: {email}\n'
                message += f'Contraseña: {password}\n'
                message += f'El perfil, pin y fechas de vencimiento siguen siendo los mismos.\n'
                message += f'Por favor, si tiene alguna duda o comentario solo escribe Hablar con un Humano o envianos un whats app al número de siempre. Saludos.'
                
                account_name_str = str(data_account.account_name)
                if hasattr(data_account.account_name, 'name'):
                    account_name_str = data_account.account_name.name
                elif hasattr(data_account.account_name, 'description'):
                    account_name_str = data_account.account_name.description
                
                if webhook_url:
                    try:
                        payload = {
                            "account_name": account_name_str,
                            "email": email,
                            "password": password,
                            "message": message,
                            "lada": customer_detail.lada,
                            "phone_number": customer_detail.phone_number
                        }
                        requests.post(webhook_url, json=payload, timeout=5)
                    except:
                        pass
                
                try:
                    Notification.send_whatsapp_notification(message, customer_detail.lada, customer_detail.phone_number)
                except:
                    pass
            except Exception as e:
                pass
    except Exception as e:
        pass

@permission_required('is_superuser', 'adm:no-permission')
def index(request):
    """
    Main Admin Page
    """
    sales_day = Dashboard.sales_per_country_day()
    sales_month = Dashboard.sales_per_country_month()
    sales_acc = Dashboard.sales_per_account()
    template_name = "adm/index.html"
    if 'date' in request.GET:
        date = datetime.strptime(request.GET['date'], '%Y-%m-%d')
    else:
        date = timezone.now().date()

    # Nuevas estadísticas de visitas
    page_visits_total = Dashboard.page_visits_by_page()
    page_visits_today_data = Dashboard.page_visits_today()
    page_visits_7days = Dashboard.page_visits_last_7_days()
    unique_visitors = Dashboard.unique_visitors_today()
    visits_chart_data = Dashboard.page_visits_last_30_days_chart()

    # Nuevas estadísticas de ventas web
    web_sales_today = Dashboard.web_sales_today()
    web_sales_weekly = Dashboard.web_sales_weekly()
    web_sales_monthly = Dashboard.web_sales_monthly()
    web_sales_yearly = Dashboard.web_sales_yearly()
    web_sales_chart = Dashboard.web_sales_last_12_months()

    return render(request, template_name, {
        'sales_day': sales_day,
        'sales_month': sales_month,
        'acc_name': sales_acc[0],
        'acc_total': sales_acc[1],
        'time': timezone.now(),
        'last_year_sales_new_user': Dashboard.last_year_sales_new_user(),
        'sales_per_day_new_user': Dashboard.sales_per_day_new_user(date),
        # Estadísticas de visitas
        'page_visits_total': page_visits_total,
        'page_visits_today': page_visits_today_data,
        'page_visits_7days': page_visits_7days,
        'unique_visitors': unique_visitors,
        'visits_chart_data': visits_chart_data,
        # Estadísticas de ventas web
        'web_sales_today': web_sales_today,
        'web_sales_weekly': web_sales_weekly,
        'web_sales_monthly': web_sales_monthly,
        'web_sales_yearly': web_sales_yearly,
        'web_sales_chart': web_sales_chart,
    })


@permission_required('is_staff', 'adm:no-permission')
def account_change_history_view(request):
    """
    Historial de cambios de cuenta con filtros y estadísticas para toma de decisiones.
    """
    template_name = 'adm/account_change_history.html'
    queryset = AccountChangeHistory.objects.select_related(
        'customer', 'changed_by', 'service', 'old_account', 'new_account', 'old_sale', 'new_sale'
    ).all()

    search = request.GET.get('search', '').strip()
    service_id = request.GET.get('service_id', '').strip()
    source = request.GET.get('source', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()

    if search:
        queryset = queryset.filter(
            Q(customer_username__icontains=search) |
            Q(customer_email__icontains=search) |
            Q(customer_phone__icontains=search) |
            Q(old_account_email__icontains=search) |
            Q(new_account_email__icontains=search)
        )

    if service_id:
        queryset = queryset.filter(service_id=service_id)

    if source:
        queryset = queryset.filter(source=source)

    if date_from:
        queryset = queryset.filter(changed_at__date__gte=date_from)

    if date_to:
        queryset = queryset.filter(changed_at__date__lte=date_to)

    total_changes = queryset.count()
    today = timezone.localdate()
    today_changes = queryset.filter(changed_at__date=today).count()
    my_account_changes = queryset.filter(source='my_account').count()
    admin_changes = queryset.filter(source='admin').count()

    service_stats = queryset.values('service__description').annotate(
        total=Count('id')
    ).order_by('-total')[:10]

    paginator = Paginator(queryset, 30)
    page = request.GET.get('page', 1)
    try:
        history_page = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        history_page = paginator.page(1)

    return render(request, template_name, {
        'history': history_page,
        'services': Service.objects.filter(status=True).order_by('description'),
        'search': search,
        'service_id': service_id,
        'source': source,
        'date_from': date_from,
        'date_to': date_to,
        'stats_total': total_changes,
        'stats_today': today_changes,
        'stats_my_account': my_account_changes,
        'stats_admin': admin_changes,
        'service_stats': service_stats,
    })

# ========== VISTAS DE DETALLE DE ESTADÍSTICAS WEB ==========

@permission_required('is_superuser', 'adm:no-permission')
def web_sales_today_detail(request):
    """
    Vista detallada de las ventas web de HOY
    """
    sales = Dashboard.get_web_sales_today_detail()
    total = sales.aggregate(Sum('payment_amount'))

    context = {
        'sales': sales,
        'total': total['payment_amount__sum'] or 0,
        'count': sales.count(),
        'period': 'Hoy',
        'period_date': timezone.now().strftime('%d/%m/%Y'),
    }
    return render(request, 'adm/web_sales_detail.html', context)

@permission_required('is_superuser', 'adm:no-permission')
def web_sales_weekly_detail(request):
    """
    Vista detallada de las ventas web de ESTA SEMANA
    """
    sales = Dashboard.get_web_sales_weekly_detail()
    total = sales.aggregate(Sum('payment_amount'))

    today = timezone.now()
    week_start = today - timedelta(days=today.weekday())

    context = {
        'sales': sales,
        'total': total['payment_amount__sum'] or 0,
        'count': sales.count(),
        'period': 'Esta Semana',
        'period_date': f"Desde {week_start.strftime('%d/%m/%Y')}",
    }
    return render(request, 'adm/web_sales_detail.html', context)

@permission_required('is_superuser', 'adm:no-permission')
def web_sales_monthly_detail(request):
    """
    Vista detallada de las ventas web de ESTE MES
    """
    sales = Dashboard.get_web_sales_monthly_detail()
    total = sales.aggregate(Sum('payment_amount'))

    month = timezone.now().month
    year = timezone.now().year

    from calendar import month_name

    context = {
        'sales': sales,
        'total': total['payment_amount__sum'] or 0,
        'count': sales.count(),
        'period': 'Este Mes',
        'period_date': f"{month_name[month]} {year}",
    }
    return render(request, 'adm/web_sales_detail.html', context)

@permission_required('is_superuser', 'adm:no-permission')
def web_sales_yearly_detail(request):
    """
    Vista detallada de las ventas web de ESTE AÑO
    """
    sales = Dashboard.get_web_sales_yearly_detail()
    total = sales.aggregate(Sum('payment_amount'))

    year = timezone.now().year

    context = {
        'sales': sales,
        'total': total['payment_amount__sum'] or 0,
        'count': sales.count(),
        'period': 'Este Año',
        'period_date': str(year),
    }
    return render(request, 'adm/web_sales_detail.html', context)


def _crm_csv_response(filename, headers, rows):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename=\"{filename}\"'
    writer = csv.writer(response)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    return response


@permission_required('is_superuser', 'adm:no-permission')
def crm_dashboard_view(request):
    """
    CRM 360: tablero analítico para decisiones de negocio.
    """
    data = CRMAnalytics.build_dashboard_data(request.GET)
    period_label = f"{data['filters']['date_from'].strftime('%d/%m/%Y')} - {data['filters']['date_to'].strftime('%d/%m/%Y')}"

    query_params = request.GET.copy()
    if 'page' in query_params:
        query_params.pop('page')
    if 'customers_page' in query_params:
        query_params.pop('customers_page')
    if 'products_page' in query_params:
        query_params.pop('products_page')
    if 'churn_page' in query_params:
        query_params.pop('churn_page')
    if 'recovered_page' in query_params:
        query_params.pop('recovered_page')
    base_query_string = query_params.urlencode()

    top_customers_paginator = Paginator(data['top_customers'], 25)
    top_products_paginator = Paginator(data['top_products'], 25)
    churn_customers_paginator = Paginator(data['churn_customers'], 25)
    recovered_customers_paginator = Paginator(data['recovered_customers'], 25)

    top_customers_page = top_customers_paginator.get_page(request.GET.get('customers_page', 1))
    top_products_page = top_products_paginator.get_page(request.GET.get('products_page', 1))
    churn_customers_page = churn_customers_paginator.get_page(request.GET.get('churn_page', 1))
    recovered_customers_page = recovered_customers_paginator.get_page(request.GET.get('recovered_page', 1))

    return render(request, 'adm/crm.html', {
        'kpis': data['kpis'],
        'filters': data['filters'],
        'options': data['options'],
        'top_customers': top_customers_page,
        'top_products': top_products_page,
        'top_products_chart': data['top_products'],
        'sales_trend': data['sales_trend'],
        'cohort_summary': data['cohort_summary'],
        'churn_customers': churn_customers_page,
        'churn_products': data['churn_products'],
        'churn_breakdown': data['churn_breakdown'],
        'recovered_customers': recovered_customers_page,
        'recovered_stats': data['recovered_stats'],
        'base_query_string': base_query_string,
        'period_label': period_label,
    })


@permission_required('is_superuser', 'adm:no-permission')
def crm_export_top_customers(request):
    sales_qs, _ = CRMAnalytics.get_filtered_sales(request.GET)
    rows = CRMAnalytics.get_top_customers(sales_qs, limit=1000)
    csv_rows = [
        [
            row['customer_id'],
            row['username'],
            row['email'],
            row['phone'],
            row['country'],
            row['currency'],
            row['total_revenue'],
            row['total_orders'],
            row['avg_ticket'],
            timezone.localtime(row['last_purchase']).strftime('%Y-%m-%d %H:%M:%S') if row['last_purchase'] else '',
        ]
        for row in rows
    ]
    return _crm_csv_response(
        'crm_top_customers.csv',
        ['customer_id', 'username', 'email', 'phone', 'country', 'currency', 'total_revenue', 'total_orders', 'avg_ticket', 'last_purchase'],
        csv_rows,
    )


@permission_required('is_superuser', 'adm:no-permission')
def crm_export_top_products(request):
    sales_qs, _ = CRMAnalytics.get_filtered_sales(request.GET)
    rows = CRMAnalytics.get_top_products(sales_qs, limit=1000)
    csv_rows = [
        [row['service_id'], row['service'], row['currency'], row['total_revenue'], row['total_orders'], row['share']]
        for row in rows
    ]
    return _crm_csv_response(
        'crm_top_products.csv',
        ['service_id', 'service', 'currency', 'total_revenue', 'total_orders', 'share'],
        csv_rows,
    )


@permission_required('is_superuser', 'adm:no-permission')
def crm_export_churn_customers(request):
    filters = CRMAnalytics.parse_filters(request.GET)
    rows = CRMAnalytics.get_churn_customers(filters, limit=5000)
    csv_rows = [
        [
            row['customer_id'],
            row['username'],
            row['email'],
            row['phone'],
            row['country'],
            row['currency'],
            timezone.localtime(row['last_purchase']).strftime('%Y-%m-%d %H:%M:%S') if row['last_purchase'] else '',
            row['days_inactive'],
            row['last_service'],
            row['total_revenue'],
            row['total_orders'],
        ]
        for row in rows
    ]
    return _crm_csv_response(
        'crm_churn_customers.csv',
        ['customer_id', 'username', 'email', 'phone', 'country', 'currency', 'last_purchase', 'days_inactive', 'last_service', 'total_revenue', 'total_orders'],
        csv_rows,
    )


@permission_required('is_superuser', 'adm:no-permission')
def crm_export_churn_products(request):
    filters = CRMAnalytics.parse_filters(request.GET)
    churn_customers = CRMAnalytics.get_churn_customers(filters, limit=5000)
    rows = CRMAnalytics.get_churn_products(churn_customers)
    csv_rows = [[row['service'], row['currency'], row['total_orders'], row['total_revenue']] for row in rows]
    return _crm_csv_response(
        'crm_churn_products.csv',
        ['service', 'currency', 'total_orders', 'total_revenue'],
        csv_rows,
    )


@permission_required('is_superuser', 'adm:no-permission')
def crm_export_recovered_customers(request):
    filters = CRMAnalytics.parse_filters(request.GET)
    rows = CRMAnalytics.get_recovered_customers(filters, limit=5000)
    csv_rows = [
        [
            row['customer_id'],
            row['username'],
            row['email'],
            row['phone'],
            row['country'],
            row['currency'],
            timezone.localtime(row['recovery_date']).strftime('%Y-%m-%d %H:%M:%S') if row['recovery_date'] else '',
            row['days_inactive_before_recovery'],
            row['service'],
            row['amount'],
        ]
        for row in rows
    ]
    return _crm_csv_response(
        'crm_recovered_customers.csv',
        ['customer_id', 'username', 'email', 'phone', 'country', 'currency', 'recovery_date', 'days_inactive_before_recovery', 'service', 'amount'],
        csv_rows,
    )

class NoPermissionView(TemplateView):
    """
    Page where are redirected users with out permissions
    """
    template_name = "adm/no_permission.html"
@permission_required('is_superuser', 'adm:no-permission')

def SettingsDetailView(request):
    """
    Here is displayed all Business Data
    """
    template_name = "adm/settings_details.html"
    try:
        business_detail = Business.objects.get(pk=1)
    except Business.DoesNotExist:
        business_detail = None
    ai_settings = AISettings.get_settings()
    return render(request, template_name, {
        'object': business_detail,
        'ai_settings': ai_settings,
    })
# @permission_required('is_superuser','adm:no-permission')

class SettingsCreateView(UserAccessMixin, CreateView):
    """
    Create Business Data once
    """
    permission_required = 'is_superuser'
    model = Business
    template_name = "adm/settings_update.html"
    form_class = SettingsForm
    success_url = reverse_lazy('adm:settings')
# @permission_required('is_superuser','adm:no-permission')

class SettingsUpdateView(UserAccessMixin, UpdateView):
    """
    Update Business Data
    """
    permission_required = 'is_superuser'
    model = Business
    template_name = "adm/settings_update.html"
    form_class = SettingsForm
    success_url = reverse_lazy('adm:settings')


@permission_required('is_superuser', 'adm:no-permission')
def AISettingsUpdateView(request):
    ai_settings = AISettings.get_settings()
    if request.method == 'POST':
        form = AISettingsForm(request.POST, instance=ai_settings)
        if form.is_valid():
            form.save()
            return redirect('adm:settings')
    else:
        form = AISettingsForm(instance=ai_settings)
    return render(
        request,
        'adm/settings_ai_update.html',
        {
            'form': form,
            'object': ai_settings,
        },
    )

@permission_required('is_staff', 'adm:no-permission')
def ProfileView(request):
    """
    Show all user info
    """
    template_name = "adm/profile_details.html"
    return render(request, template_name, {
    })

class UserdetailUpdateView(UserAccessMixin, UpdateView):
    """
    Update extra data and profile picture of users 
    """
    permission_required = 'is_staff'
    model = UserDetail
    template_name = "adm/profile_picture_update.html"
    form_class = UserDetailForm
    success_url = reverse_lazy('adm:profile')
    country = Country.get_country_lada()
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["country"] = self.country
        return context

class CustomerUpdateView(UserAccessMixin, UpdateView):
    permission_required = 'is_staff'
    template_name = 'adm/customer_update.html'
    form_class = CustomerUpdateForm
    model = UserDetail
    success_url = reverse_lazy('adm:sales')
    country = Country.get_country_lada()
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["country"] = self.country
        return context

class UserUpdateView(UserAccessMixin, UpdateView):
    """
    Update data and profile picture of users
    """
    permission_required = 'is_staff'
    model = User
    template_name = "adm/profile_update.html"
    form_class = UserForm
    success_url = reverse_lazy('adm:profile')

class MainUserUpdateView(UserAccessMixin, UpdateView):
    permission_required = 'is_staff'
    model = User
    form_class = UserMainForm
    template_name = 'adm/user_edit.html'
    success_url = reverse_lazy('adm:user')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Agregar user_detail al contexto
        try:
            context['user_detail'] = self.object.userdetail
        except:
            context['user_detail'] = None
        return context

class UserView(UserAccessMixin, ListView):
    """
    Here you can view all users of page
    """
    permission_required = 'is_staff'
    model = User
    template_name = 'adm/user.html'
    permission_required = 'is_superuser'
    paginate_by = 30

    def get_queryset(self):
        # Optimización: traer solo los campos necesarios y prefetch user_detail
        from django.db.models import Prefetch
        queryset = User.objects.only(
            'id', 'first_name', 'last_name', 'username', 'email', 
            'is_active', 'is_staff', 'is_superuser'
        ).prefetch_related(
            Prefetch('userdetail')
        )
        
        # Filtro por búsqueda (nombre, usuario o email)
        search = self.request.GET.get('search', '').strip()
        if search:
            # Optimizar búsqueda: usar iexact para términos cortos
            if len(search) == 1:
                queryset = queryset.filter(
                    Q(username__istartswith=search) |
                    Q(first_name__istartswith=search) |
                    Q(last_name__istartswith=search)
                )
            else:
                queryset = queryset.filter(
                    Q(first_name__icontains=search) |
                    Q(last_name__icontains=search) |
                    Q(username__icontains=search) |
                    Q(email__icontains=search)
                )
        
        # Filtro por estado (activo/inactivo)
        active_filter = self.request.GET.get('active_filter', '')
        if active_filter == 'active':
            queryset = queryset.filter(is_active=True)
        elif active_filter == 'inactive':
            queryset = queryset.filter(is_active=False)
        
        # Filtro por rol (staff/admin)
        role_filter = self.request.GET.get('role_filter', '')
        if role_filter == 'staff':
            queryset = queryset.filter(is_staff=True, is_superuser=False)
        elif role_filter == 'superuser':
            queryset = queryset.filter(is_superuser=True)
        elif role_filter == 'customer':
            queryset = queryset.filter(is_staff=False, is_superuser=False)
        
        # Ordenamiento
        sort = self.request.GET.get('sort', '-id')
        if sort in ['username', 'email', 'first_name', 'is_active', 'is_staff', 'id', '-username', '-email', '-first_name', '-is_active', '-is_staff', '-id']:
            queryset = queryset.order_by(sort)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search'] = self.request.GET.get('search', '')
        context['active_filter'] = self.request.GET.get('active_filter', '')
        context['role_filter'] = self.request.GET.get('role_filter', '')
        context['sort'] = self.request.GET.get('sort', '-id')
        return context

@login_required
@permission_required('is_superuser', 'adm:no-permission')
def ChangeUserPhone(request, pk):
    """
    Vista segura para cambiar el número de teléfono de un usuario
    """
    try:
        user = User.objects.get(pk=pk)
        user_detail = user.userdetail
    except (User.DoesNotExist, UserDetail.DoesNotExist):
        return redirect('adm:user')
    
    from .functions.forms import UserPhoneChangeForm
    
    if request.method == 'POST':
        form = UserPhoneChangeForm(request.POST)
        if form.is_valid():
            # Guardar datos antiguos
            old_lada = user_detail.lada
            old_phone_number = user_detail.phone_number
            
            # Actualizar con nuevos datos
            new_lada = form.cleaned_data['new_lada']
            new_phone_number = form.cleaned_data['new_phone_number']
            reason = form.cleaned_data.get('reason', '')
            
            # Actualizar el teléfono
            user_detail.lada = new_lada
            user_detail.phone_number = new_phone_number
            user_detail.save()
            
            # Registrar en el historial
            from .models import UserPhoneHistory
            UserPhoneHistory.objects.create(
                user_detail=user_detail,
                old_lada=old_lada,
                old_phone_number=old_phone_number,
                new_lada=new_lada,
                new_phone_number=new_phone_number,
                changed_by=request.user,
                reason=reason
            )
            
            # Redirigir a la vista de edición
            return redirect('adm:user_mainupdate', pk=pk)
    else:
        form = UserPhoneChangeForm(initial={
            'new_lada': user_detail.lada,
            'new_phone_number': user_detail.phone_number
        })
    
    context = {
        'form': form,
        'user': user,
        'user_detail': user_detail
    }
    return render(request, 'adm/user_phone_change.html', context)

@login_required
@permission_required('is_superuser', 'adm:no-permission')
def ToggleUserStatus(request, pk):
    """
    Cambia el estado activo/inactivo de un usuario
    """
    try:
        user = User.objects.get(pk=pk)
        user.is_active = not user.is_active
        user.save()
        
        if request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'is_active': user.is_active,
                'message': 'Estado actualizado correctamente'
            })
        else:
            return redirect(request.META.get('HTTP_REFERER', 'adm:user'))
    except User.DoesNotExist:
        if request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'message': 'Usuario no encontrado'
            }, status=404)
        return redirect('adm:user')

class ServiceView(UserAccessMixin, ListView):
    """
    Here you can see all Available Services
    """
    permission_required = 'is_staff'
    model = Service
    template_name = 'adm/services.html'
    
    def get_queryset(self):
        queryset = Service.objects.all()
        
        # Filtro por búsqueda
        search = self.request.GET.get('search', '')
        if search:
            queryset = queryset.filter(description__icontains=search)
        
        # Filtro por estado
        status_filter = self.request.GET.get('status_filter', '')
        if status_filter == 'active':
            queryset = queryset.filter(status=True)
        elif status_filter == 'inactive':
            queryset = queryset.filter(status=False)
        
        # Ordenamiento
        sort = self.request.GET.get('sort', 'description')
        
        # Manejo especial para ordenamiento de estado
        if sort == 'status_active':
            queryset = queryset.order_by('-status')  # Activos primero (True primero)
        elif sort == 'status_inactive':
            queryset = queryset.order_by('status')   # Inactivos primero (False primero)
        elif sort in ['description', 'status', 'id', '-description', '-status', '-id']:
            queryset = queryset.order_by(sort)
        else:
            queryset = queryset.order_by('description')
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search'] = self.request.GET.get('search', '')
        context['sort'] = self.request.GET.get('sort', 'description')
        context['status_filter'] = self.request.GET.get('status_filter', '')
        return context

class ServiceCreateView(UserAccessMixin, CreateView):
    """
    Create a new service
    """
    permission_required = 'is_staff'
    model = Service
    template_name = "adm/services_create.html"
    form_class = ServicesForm
    success_url = reverse_lazy('adm:services')

class ServiceUpdateView(UserAccessMixin, UpdateView):
    model = Service
    permission_required = 'is_staff'
    template_name = "adm/services_create.html"
    form_class = ServicesForm
    success_url = reverse_lazy('adm:services')

class ServiceDeleteView(UserAccessMixin, DeleteView):
    model = Service
    permission_required = 'is_staff'
    template_name = "adm/delete.html"
    success_url = reverse_lazy('adm:services')

@permission_required('is_staff', 'adm:no-permission')
def ActiveInactiveService(request, status, pk):
    service = Service.objects.get(pk=pk)
    service.status = Active_Inactive.active_inactive(status)
    service.save()
    return redirect(reverse('adm:services'))

@permission_required('is_staff', 'adm:no-permission')
def AccountsView(request):
    """
    Show all active accounts filtered by Bussiness ID of person are looking for And Pagintate by 10
    Ultra-optimized version with select_related and minimal queries (cache disabled for form objects)
    """
    business_id = request.user.userdetail.business
    template_name = 'adm/accounts.html'
    today = timezone.now().date()
    
    # Obtener filtros de POST o GET (para mantener filtros en paginación)
    account_name = request.POST.get('account_name') or request.GET.get('account_name', '')
    email = (request.POST.get('email') or request.GET.get('email', '')).replace(" ", "")
    status = request.POST.get('status') or request.GET.get('status', '')
    external_status = request.POST.get('external_status') or request.GET.get('external_status', '')
    ignore_external_status = external_status == '__ignore__'
    page = request.GET.get('page', 1)
    
    # Base queryset optimizado con select_related para evitar consultas N+1
    base_queryset = Account.objects.select_related(
        'account_name',     # Service
        'business',         # Business  
        'supplier',         # Supplier
        'customer',         # User (puede ser None)
        'created_by',       # User
        'modified_by'       # User
    ).filter(business=business_id)
    
    # Si hay filtros aplicados
    if request.method == 'POST' or any([account_name, email, status, external_status]):
        # Aplicar filtros de manera eficiente
        if account_name:
            base_queryset = base_queryset.filter(account_name=account_name)
        if email:
            base_queryset = base_queryset.filter(email__icontains=email)
        if status:
            base_queryset = base_queryset.filter(status=status == 'True')
        if external_status and not ignore_external_status:
            base_queryset = base_queryset.filter(external_status=external_status)
        
        # Ordenar de manera eficiente
        accounts = base_queryset.order_by('-created_at', 'profile')
        
        # Preparar datos del formulario
        form_data = {
            'account_name': account_name,
            'email': email,
            'status': status,
            'external_status': external_status
        }
        
        # Paginación optimizada
        p = Paginator(accounts, 20)
        
        try:
            venues = p.page(page)
        except (PageNotAnInteger, EmptyPage):
            venues = p.page(1)
        
        # Query string optimizado
        filter_params = []
        if account_name:
            filter_params.append(f'account_name={account_name}')
        if email:
            filter_params.append(f'email={email}')
        if status:
            filter_params.append(f'status={status}')
        if external_status:
            filter_params.append(f'external_status={external_status}')

        filter_query = '&'.join(filter_params)
        
        # Crear contexto sin objetos que no se pueden serializar
        context = {
            "venues": venues,
            "form": FilterAccountForm(),
            "external_status_choices": Account._meta.get_field('external_status').choices,
            "today": today,
            "form_data": form_data,
            "filter_query": filter_query,
            "has_filters": True
        }
        
        return render(request, template_name, context)
    
    else:
        # Sin filtros - caso más común, altamente optimizado
        accounts = base_queryset.filter(
            status=True, 
            customer__isnull=True
        ).order_by('-created_at', 'profile')
        
        # Paginación
        p = Paginator(accounts, 20)
        
        try:
            venues = p.page(page)
        except (PageNotAnInteger, EmptyPage):
            venues = p.page(1)
        
        context = {
            "venues": venues,
            "form": FilterAccountForm(),
            "external_status_choices": Account._meta.get_field('external_status').choices,
            "today": today,
            "has_filters": False
        }
        
        return render(request, template_name, context)

@permission_required('is_staff', 'adm:no-permission')
def AccountsCreateView(request):
    """
    Create a new Account
    """
    template_name = 'adm/accounts_create.html'
    form_class = AccountsForm(request.POST or None)
    success_url = reverse_lazy('adm:accounts')
    related_accounts = None
    # Determinar datos para buscar cuentas relacionadas
    if request.method == 'POST':
        account_name_id = request.POST.get('account_name')
        email = request.POST.get('email')
        password = request.POST.get('password')
        if account_name_id and email and password:
            try:
                account_name = Service.objects.get(pk=account_name_id)
                related_accounts = Account.objects.filter(account_name=account_name, email=email, password=password)
            except Service.DoesNotExist:
                related_accounts = None
        business = Business.objects.get(pk=request.POST.get('business'))
        supplier = Supplier.objects.get(pk=request.POST.get('supplier'))
        created_by = User.objects.get(pk=request.POST.get('created_by'))
        modified_by = User.objects.get(pk=request.POST.get('modified_by'))
        account_name = Service.objects.get(pk=request.POST.get('account_name'))
        expiration_date = request.POST.get('expiration_date')
        # Convertir a datetime aware si es necesario
        if expiration_date:
            if isinstance(expiration_date, str):
                try:
                    expiration_date_dt = datetime.strptime(expiration_date, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    try:
                        expiration_date_dt = datetime.strptime(expiration_date, "%Y-%m-%d")
                    except ValueError:
                        expiration_date_dt = None
                if expiration_date_dt:
                    if timezone.is_naive(expiration_date_dt):
                        expiration_date = timezone.make_aware(expiration_date_dt)
                    else:
                        expiration_date = expiration_date_dt
        # Si no es string, se asume que ya es datetime
        comments = request.POST.get('comments')
        renovable = request.POST.get('renovable') == 'on'

        # Obtener campos adicionales
        external_status = request.POST.get('external_status', 'Disponible')
        pin_value = request.POST.get('pin')
        pin = int(pin_value) if pin_value and pin_value.strip() else None

        profile = account_name.perfil_quantity
        for i in range(profile+1):
            if i == 0:
                continue
            acc = Account.objects.create(
                business=business,
                supplier=supplier,
                account_name=account_name,
                expiration_date=expiration_date,
                email=email,
                password=password,
                comments=comments,
                renovable=renovable,
                created_by=created_by,
                modified_by=modified_by,
                profile=i,
                external_status=external_status,
                pin=pin
            )
        return redirect(success_url)
    else:
        # GET: Si hay datos en el formulario, buscar relacionados
        account_name_id = request.GET.get('account_name') or None
        email = request.GET.get('email') or None
        password = request.GET.get('password') or None
        if account_name_id and email and password:
            try:
                account_name = Service.objects.get(pk=account_name_id)
                related_accounts = Account.objects.filter(account_name=account_name, email=email, password=password)
            except Service.DoesNotExist:
                related_accounts = None
    return render(request, template_name, {
        'form': form_class,
        'related_accounts': related_accounts
    })

@permission_required('is_staff', 'adm:no-permission')
def AccountsUpdateView(request, pk):
    """
    Create a new Account
    """
    template_name = 'adm/accounts_create.html'
    accounts = Account.objects.get(pk=pk)
    form_class = AccountsForm(request.POST or None, instance=accounts)
    success_url = reverse_lazy('adm:accounts')
    if request.method == 'POST':
        supplier = Supplier.objects.get(pk=request.POST.get('supplier'))
        modified_by = User.objects.get(pk=request.POST.get('modified_by'))
        account_name = Service.objects.get(pk=request.POST.get('account_name'))
        expiration_date = request.POST.get('expiration_date')
        # Convertir a datetime aware si es necesario
        if expiration_date:
            if isinstance(expiration_date, str):
                try:
                    expiration_date_dt = datetime.strptime(expiration_date, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    try:
                        expiration_date_dt = datetime.strptime(expiration_date, "%Y-%m-%d")
                    except ValueError:
                        expiration_date_dt = None
                if expiration_date_dt:
                    if timezone.is_naive(expiration_date_dt):
                        expiration_date = timezone.make_aware(expiration_date_dt)
                    else:
                        expiration_date = expiration_date_dt
        # Si no es string, se asume que ya es datetime
        email = request.POST.get('email')
        password = request.POST.get('password')
        comments = request.POST.get('comments')
        renewal_date = request.POST.get('renewal_date')
        if request.POST.get('renovable') == 'on':
            renovable = True
        else:
            renovable = False
        old = Account.objects.get(pk=pk)
        # Guardar la contraseña anterior para comparar
        old_password = old.password
        acc = Account.objects.filter(
            account_name=old.account_name,
            email=old.email
        )
        # Verificar si la contraseña cambió
        password_changed = old_password != password
        
        for a in acc:
            a.supplier = supplier
            a.modified_by = modified_by
            a.account_name = account_name
            # Asegurar aware
            if expiration_date and isinstance(expiration_date, str):
                try:
                    expiration_date_dt = datetime.strptime(expiration_date, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    try:
                        expiration_date_dt = datetime.strptime(expiration_date, "%Y-%m-%d")
                    except ValueError:
                        expiration_date_dt = None
                if expiration_date_dt:
                    if timezone.is_naive(expiration_date_dt):
                        expiration_date = timezone.make_aware(expiration_date_dt)
                    else:
                        expiration_date = expiration_date_dt
            a.expiration_date = expiration_date
            a.email = email
            a.password = password
            a.comments = comments
            a.renovable = renovable
            a.renewal_date = renewal_date
            if request.POST.get('status') == 'on':
                a.status = True
            a.save()
            
        # Enviar webhook de N8N solo si la contraseña cambió
        if password_changed:
            webhook_url = os.environ.get("N8N_WEBHOOK_URL_CHANGE_PASSWORD")
            account_name_str = str(account_name)
            if hasattr(account_name, 'name'):
                account_name_str = account_name.name
            elif hasattr(account_name, 'description'):
                account_name_str = account_name.description
            payload = {
                "account_name": account_name_str,
                "email": email,
                "password": password,
                "message": "Contraseña actualizada.",
                "lada": None,
                "phone_number": None
            }
            if webhook_url:
                try:
                    requests.post(webhook_url, json=payload)
                except Exception as e:
                    print(f"Error enviando webhook N8N: {e}")
        return redirect(success_url)
    else:
        return render(request, template_name, {
            'form': form_class
        })

@permission_required('is_staff', 'adm:no-permission')
def AccountsExpiredView(request):
    """
    Show all active accounts filtered by Bussiness ID of person are looking for, expiration date And Pagintate by 10
    """
    business_id = request.user.userdetail.business
    template_name = 'adm/accounts_expired.html'
    today = timezone.now().date()
    form = FilterAccountForm()
    if request.method == 'POST':
        date = request.POST['vencimiento'].replace(" ", "")
        status = request.POST['status']
        if not date:
            if not status:
                accounts = Account.objects.filter(
                    business=business_id,
                    expiration_date__lte=today
                )
            else:
                accounts = Account.objects.filter(
                    business=business_id,
                    status=status,
                    expiration_date__lte=today
                )
        else:
            if not status:
                accounts = Account.objects.filter(
                    business=business_id,
                    expiration_date=date
                )
            else:
                accounts = Account.objects.filter(
                    business=business_id,
                    status=status,
                    expiration_date=date
                )
            # Set Up Pagination
        accounts = NoDuplicate.no_duplicate(accounts)
        p = Paginator(accounts, 10000)
        page = request.GET.get('page')
        venues = p.get_page(page)
        return render(request, template_name, {
            "accounts": accounts,
            "venues": venues,
            "form": form
        })
    else:
        active = 1
        accounts = Account.objects.filter(
            business=business_id, expiration_date__lte=today)
        acc = NoDuplicate.no_duplicate(accounts)
        # Set Up Pagination
        p = Paginator(acc, 7)
        page = request.GET.get('page')
        venues = p.get_page(page)
        return render(request, template_name, {
            "accounts": accounts,
            "venues": venues,
            "form": form
        })
def clean_phone_number(phone):
    """
    Limpia y formatea el número de teléfono según el país
    +521XXXXXXXXXX -> últimos 10 dígitos (México)
    +56XXXXXXXX -> últimos 8 dígitos (Chile)
    Otros -> últimos 10 dígitos
    """
    if not phone:
        return None
        
    # Eliminar espacios y caracteres no numéricos excepto '+'
    phone = ''.join(c for c in str(phone) if c.isdigit() or c == '+')
    
    if phone.startswith('+521'):  # México
        return phone[-10:] if len(phone) >= 10 else phone
    elif phone.startswith('+56'):  # Chile
        return phone[-8:] if len(phone) >= 8 else phone
    else:  # Otros países
        return phone[-10:] if len(phone) >= 10 else phone

# Función para validar el token de iframe
def validate_iframe_token(token):
    """
    Valida si el token recibido es válido para acceso iframe
    """
    from django.conf import settings
    valid_token = getattr(settings, 'IFRAME_ACCESS_TOKEN', None)
    return token and valid_token and token == valid_token

def SalesView(request, phone_number=None):
    import logging
    import sys
    from datetime import datetime
    
    # Múltiples métodos de logging para asegurar visibilidad
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_msg = f"[{timestamp}] SalesView - GET: {dict(request.GET)} - URL: {request.get_full_path()}"
    
    # 1. Print normal
    print("=== SALESVIEW CALLED ===")
    print(log_msg)
    
    # 2. Print a stderr
    print(log_msg, file=sys.stderr)
    
    # 3. Logging de Django
    logger = logging.getLogger('django')
    logger.error(log_msg)  # Usar error para que sea más visible
    
    # 4. Archivo de log
    try:
        with open('/tmp/django_debug.log', 'a') as f:
            f.write(log_msg + '\n')
    except:
        pass
    
    # Verificar el token primero
    iframe_token = request.GET.get('token')
    if not validate_iframe_token(iframe_token) and not request.user.is_staff:
        return redirect('adm:no-permission')
    template_name = 'adm/sale.html'
    
    response = None
    
    # Obtener número de teléfono ya sea de path parameter o query parameter y limpiarlo
    phone_number = clean_phone_number(phone_number or request.GET.get('phone_number'))
    
    # Manejar número de teléfono si existe
    if phone_number:
        try:
            # Convertir a entero para la búsqueda en la base de datos
            phone_number_int = int(phone_number)
            # Buscar usuario por número de teléfono
            customer_detail = UserDetail.objects.get(phone_number=phone_number_int)
            return Sales.render_view(request, customer=customer_detail.user.id)
        except (UserDetail.DoesNotExist, ValueError):
            # Si no existe el usuario o el número no es válido, simular un POST
            request.method = 'POST'
            request.POST = request.POST.copy()
            request.POST['customer'] = str(phone_number)
            request.POST._mutable = False
    if request.method == 'POST':
        try:
            customer = Sales.is_email(request, request.POST.get('customer'))
        except NameError:
            message = "Número de telefono invalido, tiene más carácteres de los permitidos."
            response = Sales.render_view(request, message=message)
            response.delete_header('X-Frame-Options')
            return response
        except TypeError:
            message = 'El email ingresado no tiene el formato correcto, debe incluir "@"'
            response = Sales.render_view(request, message=message)
            response.delete_header('X-Frame-Options')
        if customer == 'phone':
            template_name = 'adm/user_new_customer.html'
            customer = request.POST.get('customer').replace(" ", "")
            if request.POST.get('new-customer') == 'yes':
                customer = request.POST.get('customer')
                current_datetime = timezone.now()-timedelta(hours=6)
                user = User.objects.create_user(
                    customer, 'example@example.com', 'cuentasmexico', date_joined=current_datetime)
                user.date_joined = current_datetime
                user.save()
                user_detail = UserDetail.objects.create(
                    business=request.user.userdetail.business, user=user, phone_number=int(customer), lada=0, country="??")
                return redirect(reverse('adm:user_reference', args=(user_detail.id,)))
            return render(request, template_name, {
                'customer': customer
            })
        if customer == 'email':
            template_name = 'adm/user_new_customer.html'
            customer = request.POST.get('customer').replace(" ", "")
            if request.POST.get('new-customer') == 'yes':
                customer = request.POST.get('customer')
                current_datetime = timezone.now()-timedelta(hours=6)
                user = User.objects.create_user(
                    customer, customer, 'cuentasmexico', date_joined=current_datetime)
                user.date_joined = current_datetime
                user.save()
                user_detail = UserDetail.objects.create(
                    business=request.user.userdetail.business, user=user, phone_number=0, lada=0, country="??")
                return redirect(reverse('adm:user_reference', args=(user_detail.id,)))
            return render(request, template_name, {
                'customer': customer
            })
        try:
            customer.country
            # return redirect(reverse('adm:user_update',args=(customer.id,)))
            return redirect(reverse('adm:user_reference', args=(customer.id,)))
        except AttributeError:
            return Sales.render_view(request, customer.id)
    else:
        # Manejar navegación de paginación con cliente específico
        customer_id = request.GET.get('customer')
        if customer_id:
            try:
                customer_detail = UserDetail.objects.get(pk=customer_id)
                return Sales.render_view(request, customer=customer_detail.user.id)
            except (UserDetail.DoesNotExist, ValueError):
                # Si el customer_id no es válido, mostrar vista sin cliente
                pass
        
        response = render(request, template_name, {
            'availables': Sales.availables()[0]
        })
        # Permitir que la vista se muestre en iframes desde cualquier origen
        response.xframe_options_exempt = True
        del response['X-Frame-Options']
        return response

def key_adjust(request, pk):
    template_name = 'adm/key_adjust.html'
    if request.method == 'POST':
        days = int(request.POST.get('days'))
        sale = Sale.objects.get(pk=pk)
        expiration_date = sale.expiration_date
        new_date = expiration_date + timedelta(days=days)
        # Asegurar aware
        if timezone.is_naive(new_date):
            new_date = timezone.make_aware(new_date)
        sale.expiration_date = new_date
        sale.save()
        account_name = sale.account.account_name
        accont_email = sale.account.email
        message = f"Hemos ajustado la fecha de vencimiento, de tu cuenta {account_name} con email {accont_email} ahora vence el {new_date.strftime('%d/%m/%Y')}"
        customer_detail = UserDetail.objects.get(user=sale.customer.id)
        Notification.send_whatsapp_notification(message,customer_detail.lada,customer_detail.phone_number)
        return redirect(reverse_lazy('adm:sales'))
    return render(request, template_name, {
        'pk': pk
    })

def SalesAddFreeDaysView(request, pk, days):
    sale = Sale.objects.get(pk=pk)
    new_expiration = sale.expiration_date + timedelta(days=days)
    if timezone.is_naive(new_expiration):
        new_expiration = timezone.make_aware(new_expiration)
    sale.expiration_date = new_expiration
    sale.save()
    customer = UserDetail.objects.get(user=sale.customer.id)
    customer.free_days = 0
    customer.save()
    try:
        if days > 0:
            title = f"Felicidades, has ganado {days} días gratis"
            token = customer.token
            body = f"Los días ya fueron cargados a tu cuneta. Puedes ver tu nueva fecha de vencimiento en la sección de Mi Cuenta"
            url = "MyAccount"
            notification = send_push_notification(
                token, title, body, url)
            print(notification)
    except:
        pass
    return Sales.render_view(request, sale.customer.id)

@permission_required('is_staff', 'adm:no-permission')
def UserReferenceView(request, pk):
    template_name = "adm/user_reference.html"
    customer_reference = pk
    message = ''
    if request.method == 'POST':
        reference_phone = request.POST.get('reference')
        try:
            user = UserDetail.objects.get(phone_number=reference_phone)
            user.free_days += 7
            user.reference_used = False
            user.save()
            customer = UserDetail.objects.get(pk=pk)
            customer.free_days += 7
            customer.reference = user.id
            customer.reference_used = False
            print('si entro')
            customer.save()
            return redirect(reverse('adm:user_update', args=(pk,)))
        except UserDetail.DoesNotExist:
            message = "El cliente ingresado no existe"
    return render(request, template_name, {
        'customer_reference': customer_reference,
        'pk': pk,
        'message': message
    })

@permission_required('is_staff', 'adm:no-permission')
def SalesCreateView(request, pk):
    template_name = 'adm/sale_create.html'
    bank = Bank.objects.filter(status=True)
    payment = PaymentMethod.objects.all()
    message = None
    if request.method == 'POST':
        if not request.POST.getlist('serv'):
            message = 'Debes seleccionar al menos un servicio para terminar la venta.'
        elif Sales.new_sale(request) == True:
            # Obtener el cliente y redirigir a su página de ventas
            customer = User.objects.get(pk=pk)
            return Sales.render_view(request, customer.id)
        else:
            message = 'No se pudo crear la venta. Verifica los datos e intenta nuevamente.'
    return render(request, template_name, {
        'customer': User.objects.get(pk=pk),
        'services': Sales.availables()[1],
        'bank': bank,
        'payment': payment,
        'availables': Sales.availables()[0],
        'created_at': timezone.now(),
        'message': message
    })

@permission_required('is_staff', 'adm:no-permission')
def SalesUpdateStatusView(request, pk, customer, status):
    sale = Sale.objects.get(pk=pk)
    sale.status = Active_Inactive.active_inactive(status)
    sale.expiration_date = timezone.now()
    sale.save()
    acc = sale.account
    acc.customer = None
    acc.save()
    return Sales.render_view(request, customer)

@csrf_exempt
@permission_required('is_staff', 'adm:no-permission')
def SalesSearchView(request):
    logger = logging.getLogger('django')
    
    if is_ajax(request):
        services = request.POST.getlist('data[]', '')
        page = int(request.POST.get('page', 1))
        items_per_page = 20
        
        if not services:
            return JsonResponse({'data': "No hay cuentas seleccionadas"})
        
        # Recolectar todas las cuentas de todos los servicios
        all_accounts = []
        
        for s in services:
            service_data = json.loads(s)
            service_id = service_data['service']
            
            service = Service.objects.get(pk=int(service_id))
            
            # Obtener todas las cuentas para este servicio
            accounts_query = Account.objects.filter(
                account_name=service, 
                customer=None, 
                status=True,
                external_status='Disponible'
            ).select_related('account_name').only(
                'id', 'email', 'password', 'expiration_date', 'profile', 'account_name'
            ).annotate(
                email_priority=Case(
                    When(email__iendswith='@berberdna.tn', then=1),
                    When(email__iendswith='@mangosvip.com', then=2),
                    When(email__iendswith='@thortry.com', then=3),
                    When(email__iendswith='@gmail.com', then=5),
                    default=4,
                    output_field=IntegerField(),
                )
            ).order_by('email_priority', '-expiration_date')
            
            for acc in accounts_query:
                logo_url = acc.account_name.logo.url
                logger.info(f"[SalesSearch] Enviando logo URL: {logo_url}")
                all_accounts.append({
                    'id': acc.id,
                    'logo': logo_url,
                    'acc_name': acc.account_name.description,
                    'email': acc.email,
                    'password': acc.password,
                    'expiration_acc': acc.expiration_date,
                    'profile': acc.profile
                })
        
        total_count = len(all_accounts)
        
        if not all_accounts:
            return JsonResponse({
                'data': "No hay cuentas disponibles",
                'total': 0
            })
        
        # Devolver TODAS las cuentas sin paginar para que el filtro funcione correctamente
        return JsonResponse({
            'data': all_accounts,
            'total': total_count
        })
    elif request.method == 'POST':
        data_array = []
        data = json.loads(request.body)
        service_id = int(data['data']['service'])
        code_name = data['data']['code']
        code = Cupon.objects.get(name=normalize_code(code_name))
        service = Service.objects.get(pk=service_id)
        accounts = Account.objects.filter(
            account_name=service, customer=None, status=True, external_status='Disponible').order_by('-expiration_date')
        better_acc_expiration_date = code.get_expiration_date(timezone.now())
        better_acc = Sales.search_better_acc(
            service.id, better_acc_expiration_date)
        if better_acc[0] == False:
            return JsonResponse({'data': 'No hay cuentas disponibles'})
        else:
            data_array.append({
                'id': better_acc[1].id,
                'logo': better_acc[1].account_name.logo.url,
                'acc_name': better_acc[1].account_name.description,
                'email': better_acc[1].email,
                'password': better_acc[1].password,
                'expiration_acc': better_acc[1].expiration_date,
                'profile': better_acc[1].profile
            })
            for other_acc in accounts:
                if other_acc.id != better_acc[1].id:
                    item = {
                        'id': other_acc.id,
                        'logo': other_acc.account_name.logo.url,
                        'acc_name': other_acc.account_name.description,
                        'email': other_acc.email,
                        'password': other_acc.password,
                        'expiration_acc': other_acc.expiration_date,
                        'profile': other_acc.profile
                    }
                    data_array.append(item)
        if len(accounts) == 0 and len(services) == 0:
            data_array = "No Hay cuentas disponibles"
        return JsonResponse({'data': data_array})
    return JsonResponse({})

@permission_required('is_staff', 'adm:no-permission')
def SalesSearchDetailView(request):
    if is_ajax(request):
        res = None
        services = request.POST.getlist('det[]', '')
        data = []
        if services:
            for s in services:
                account = Account.objects.get(pk=s)
                det = Account.objects.filter(
                    account_name=account.account_name, email=account.email, password=account.password)
                print(account.id)
                if len(det) > 0 and len(services) > 0:
                    for pos in det:
                        # try:
                        customer_end_date = Sale.objects.filter(
                            account=pos.id, customer=pos.customer)  # .expiration_date
                        if customer_end_date:
                            for c in customer_end_date:
                                if c:
                                    customer_end_date = c.expiration_date.date().strftime('%d/%m/%Y')
                                else:
                                    customer_end_date = 'Disponible'
                                # except Sale.DoesNotExist:
                                #     customer_end_date = 'Disponible'
                                # except AttributeError:
                                #     customer_end_date = 'Disponible'
                        else:
                            customer_end_date = 'Disponible'
                        if pos.customer:
                            customer = User.objects.get(
                                pk=pos.customer.id).userdetail.phone_number
                        else:
                            customer = None
                        #
                        item = {
                            'id': pos.id,
                            'logo': pos.account_name.logo.url,
                            'email': pos.email,
                            'profile': pos.profile,
                            'status': pos.status,
                            'customer': customer,
                            'customer_end_date': customer_end_date
                        }
                        if item not in data:
                            data.append(item)
                        else:
                            continue
                    det = data
                else:
                    det = "No hay cuentas disponibles"
            # print(det)
            return JsonResponse({'det': det})
        else:
            det = "No hay cuentas seleccionadas"
        return JsonResponse({'det': det})
    return JsonResponse({})

@permission_required('is_staff', 'adm:no-permission')
def RenewView(request, pk):
    template_name = 'adm/sales_renew.html'
    sale = Sale.objects.get(pk=pk)
    banklist = Bank.objects.filter(status=True)
    paymentmethodlist = PaymentMethod.objects.all()
    if request.method == 'POST':
        if Sales.renew_sale(request, pk) == True:
            customer = Sale.objects.get(pk=pk).customer
            return Sales.render_view(request, customer)
    return render(request, template_name, {
        'object': sale,
        'banklist': banklist,
        'paymentmethodlist': paymentmethodlist
    })

@permission_required('is_staff', 'adm:no-permission')
def SalesChangeView(request, pk):
    template_name = 'adm/sale_change.html'
    bank = Bank.objects.filter(status=True)
    payment = PaymentMethod.objects.all()
    sale = Sale.objects.get(pk=pk)

    # Obtener el servicio seleccionado (por defecto el servicio actual de la venta)
    selected_service_id = request.GET.get('service_id', sale.account.account_name.id)

    # Filtrar cuentas por el servicio seleccionado
    accounts = Account.objects.filter(
        account_name_id=selected_service_id,
        status=True,
        customer=None,
        external_status='Disponible'
    ).order_by('profile')

    # Obtener todos los servicios activos
    services = Service.objects.filter(status=True).order_by('description')

    if request.method == 'POST':
        if Sales.change_sale(request) == True:
            customer = sale.customer
            return Sales.render_view(request, customer)

    return render(request, template_name, {
        'customer': Sale.objects.get(pk=pk).customer,
        'sale': sale,
        'accounts': accounts,
        'services': services,
        'selected_service_id': int(selected_service_id),
        'availables': Sales.availables()[0]
    })

def OldAccView(request, sale):
    template_name = 'adm/archive.html'
    sale_data = Sale.objects.get(pk=sale)
    new_data = Sale.objects.get(pk=sale_data.old_acc)
    return render(request, template_name, {
        'data': sale_data,
        'new_data': new_data
    })

def CheckTicket(request):
    if is_ajax(request):
        data = None
        ticket = request.POST.get('data')
        used = Sale.objects.filter(invoice=ticket)
        if used:
            data = []
            for u in used:
                my_dict = {
                    'email': u.account.email,
                    'customer': u.customer.userdetail.phone_number,
                    'date': u.created_at,
                    'ticket': u.invoice
                }
                data.append(my_dict)
            return JsonResponse({'data': data})
        else:
            return JsonResponse({'data': data})

class ProfileUpdateView(UserAccessMixin, UpdateView):
    """
    Update aprofile number
    """
    permission_required = 'is_staff'
    model = Account
    template_name = "adm/accounts_profile.html"
    success_url = reverse_lazy('adm:accounts')
    fields = ['profile']

def BankListView(request):
    """
    Mostrar todas las cuentas bancarias
    """
    template_name = "adm/bank.html"
    banks = Bank.objects.all()
    object_list = []
    for bank in banks:
        month = datetime.now().month
        _, last_day = monthrange(2023, month)
        start_date = timezone.make_aware(datetime(2023, month, 1))
        end_date = timezone.make_aware(datetime(2023, month, last_day, 23, 59, 59, 999999))
        sales = Sale.objects.filter(
            bank=bank,
            created_at__range=(start_date, end_date)
        ).aggregate(Sum('payment_amount'))
        item = {
            'pk': bank.pk,
            'logo': bank.logo,
            'bank_name': bank.bank_name,
            'headline': bank.headline,
            'card_number': bank.card_number,
            'clabe': bank.clabe,
            'total': sales['payment_amount__sum'],
            'status': bank.status,
        }
        object_list.append(item)
    return render(request, template_name, {'object_list': object_list})
class bankCreateView(UserAccessMixin, CreateView):
    """
    Create a new Bank Account
    """
    permission_required = 'is_staff'
    model = Bank
    template_name = "adm/bank_create.html"
    success_url = reverse_lazy('adm:bank')
    form_class = BankForm

class BankUpdateView(UserAccessMixin, UpdateView):
    """
    Update a existent bank account
    """
    permission_required = 'is_staff'
    model = Bank
    template_name = "adm/bank_create.html"
    success_url = reverse_lazy('adm:bank')
    form_class = BankForm

class BankDeleteView(UserAccessMixin, DeleteView):
    """
    Delete a Bank Account
    """
    permission_required = 'is_staff'
    model = Bank
    template_name = "adm/delete.html"
    success_url = reverse_lazy('adm:bank')

class PaymentMethodListView(UserAccessMixin, ListView):
    """
    Show all payment methods
    """
    permission_required = 'is_staff'
    model = PaymentMethod
    template_name = "adm/payment_method.html"

class PaymentMethodCreateView(UserAccessMixin, CreateView):
    """
    Create a new Payment Method
    """
    permission_required = 'is_staff'
    model = PaymentMethod
    template_name = "adm/payment_method_create.html"
    success_url = reverse_lazy('adm:payment_method')
    form_class = PaymentMethodForm

class PaymentMethodUpdateView(UserAccessMixin, UpdateView):
    """
    Update a existent Payment Method
    """
    permission_required = 'is_staff'
    model = PaymentMethod
    template_name = "adm/payment_method_create.html"
    success_url = reverse_lazy('adm:payment_method')
    form_class = PaymentMethodForm

class PaymentMethodDeleteView(UserAccessMixin, DeleteView):
    permission_required = 'is_staff'
    model = PaymentMethod
    template_name = "adm/delete.html"
    success_url = reverse_lazy('adm:payment_method')

class StatusListView(UserAccessMixin, ListView):
    permission_required = 'is_staff'
    model = Status
    template_name = "adm/status.html"

class StatusCreateView(UserAccessMixin, CreateView):
    permission_required = 'is_staff'
    model = Status
    template_name = "adm/status_create.html"
    success_url = reverse_lazy('adm:status')
    form_class = StatusForm

class StatusUpdateView(UserAccessMixin, UpdateView):
    permission_required = 'is_staff'
    model = Status
    template_name = "adm/status_create.html"
    success_url = reverse_lazy('adm:status')
    form_class = StatusForm

class StatusDeleteView(UserAccessMixin, DeleteView):
    permission_required = 'is_staff'
    model = Status
    template_name = "adm/delete.html"
    success_url = reverse_lazy('adm:status')

class SupplierListView(UserAccessMixin, ListView):
    permission_required = 'is_staff'
    model = Supplier
    template_name = "adm/supplier.html"

class SupplierCreateView(UserAccessMixin, CreateView):
    permission_required = 'is_staff'
    model = Supplier
    template_name = "adm/supplier_create.html"
    success_url = reverse_lazy('adm:supplier')
    form_class = SupplierForm

class SupplierUpdateView(UserAccessMixin, UpdateView):
    permission_required = 'is_staff'
    model = Supplier
    template_name = "adm/supplier_create.html"
    success_url = reverse_lazy('adm:supplier')
    form_class = SupplierForm

class SupplierDeleteView(UserAccessMixin, DeleteView):
    permission_required = 'is_staff'
    model = Supplier
    template_name = "adm/delete.html"
    success_url = reverse_lazy('adm:supplier')

def _legacy_long_from_duration(duration_unit, duration_quantity):
    if duration_unit == Cupon.DURATION_UNIT_YEAR:
        return duration_quantity * 12
    if duration_unit == Cupon.DURATION_UNIT_MONTH:
        return duration_quantity
    # Compatibilidad temporal: para day/week mantenemos 1 mes aproximado en legacy.
    return 1


class CuponView(UserAccessMixin, ListView):
    permission_required = 'is_staff'
    model = Cupon
    template_name = "adm/cupon.html"
    paginate_by = 20

    def get_queryset(self):
        queryset = Cupon.objects.select_related('customer', 'seller', 'order').order_by('-create_date')
        search = self.request.GET.get('search', '').strip().lower()
        status_filter = self.request.GET.get('status', '').strip()
        duration_filter = self.request.GET.get('duration', '').strip()

        if search:
            queryset = queryset.filter(name__icontains=search)
        if status_filter in ('active', 'inactive'):
            queryset = queryset.filter(status=(status_filter == 'active'))
        if duration_filter:
            queryset = queryset.filter(duration_unit=duration_filter)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_form'] = CuponForm()
        context['search'] = self.request.GET.get('search', '').strip()
        context['status_filter'] = self.request.GET.get('status', '').strip()
        context['duration_filter'] = self.request.GET.get('duration', '').strip()
        context['duration_choices'] = Cupon.DURATION_UNIT_CHOICES
        return context


@permission_required('is_staff', 'adm:no-permission')
def CuponCreateView(request):
    if request.method != 'POST':
        return redirect(reverse('adm:cupon'))

    form = CuponForm(request.POST)
    if form.is_valid():
        cupon = form.save(commit=False)
        cupon.long = _legacy_long_from_duration(cupon.duration_unit, cupon.duration_quantity)
        cupon.used_count = 0
        cupon.save()
        return redirect(reverse('adm:cupon'))

    queryset = Cupon.objects.order_by('-create_date')
    paginator = Paginator(queryset, 20)
    venues = paginator.get_page(1)
    return render(request, "adm/cupon.html", {
        'object_list': venues,
        'page_obj': venues,
        'is_paginated': venues.has_other_pages(),
        'create_form': form,
        'duration_choices': Cupon.DURATION_UNIT_CHOICES,
    })


@permission_required('is_staff', 'adm:no-permission')
def CuponUpdateView(request, pk):
    cupon = Cupon.objects.get(pk=pk)
    if request.method == 'POST':
        form = CuponForm(request.POST, instance=cupon)
        if form.is_valid():
            updated = form.save(commit=False)
            updated.long = _legacy_long_from_duration(updated.duration_unit, updated.duration_quantity)
            if updated.max_uses > 0 and updated.used_count > updated.max_uses:
                updated.used_count = updated.max_uses
            updated.save()
            return redirect(reverse('adm:cupon'))
    else:
        form = CuponForm(instance=cupon)

    return render(request, 'adm/cupon_form.html', {
        'form': form,
        'cupon': cupon,
    })


@permission_required('is_staff', 'adm:no-permission')
def CuponToggleStatusView(request, pk):
    cupon = Cupon.objects.get(pk=pk)
    cupon.status = not cupon.status
    cupon.save(update_fields=['status'])
    return redirect(reverse('adm:cupon'))


class CouponRedemptionLogView(UserAccessMixin, ListView):
    permission_required = 'is_staff'
    model = CouponRedemption
    template_name = "adm/coupon_redemptions.html"
    paginate_by = 30

    def get_queryset(self):
        queryset = CouponRedemption.objects.select_related('cupon', 'customer', 'sale').order_by('-redeemed_at')
        search = self.request.GET.get('search', '').strip()
        channel = self.request.GET.get('channel', '').strip()
        date_from = self.request.GET.get('date_from', '').strip()
        date_to = self.request.GET.get('date_to', '').strip()

        if search:
            queryset = queryset.filter(
                Q(cupon__name__icontains=search) |
                Q(customer__username__icontains=search) |
                Q(phone_number__icontains=search) |
                Q(service_name__icontains=search)
            )
        if channel in (CouponRedemption.CHANNEL_WEB, CouponRedemption.CHANNEL_ADMIN):
            queryset = queryset.filter(channel=channel)
        if date_from:
            queryset = queryset.filter(redeemed_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(redeemed_at__date__lte=date_to)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search'] = self.request.GET.get('search', '').strip()
        context['channel'] = self.request.GET.get('channel', '').strip()
        context['date_from'] = self.request.GET.get('date_from', '').strip()
        context['date_to'] = self.request.GET.get('date_to', '').strip()
        context['channel_choices'] = CouponRedemption.CHANNEL_CHOICES
        return context

@permission_required('is_staff', 'adm:no-permission')
def CuponRedeemView(request):
    template_name = "adm/cupon_redeem.html"
    error = None
    services = None
    cupon = None
    if request.method == 'POST':
        code_name = normalize_code(request.POST.get('code'))
        customer = request.POST.get('customer')
        service = request.POST.get('service')
        customer_user = User.objects.get(pk=customer)
        if service:
            try:
                cupon = validate_coupon_from_code(code_name, customer_user)
                return render(request, template_name, {
                    'service': service,
                    'cupon': cupon,
                    'customer': customer,
                    'duration_label': cupon.get_duration_unit_display(),
                    'duration_quantity': cupon.duration_quantity,
                })
            except (Cupon.DoesNotExist, CouponRedeemError) as exc:
                return render(request, template_name, {
                    'error': str(exc),
                    'customer': customer,
                })
        try:
            cupon = validate_coupon_from_code(code_name, customer_user)
            services = Service.objects.filter(status=True)
        except (Cupon.DoesNotExist, CouponRedeemError) as exc:
            error = str(exc)
        return render(request, template_name, {
            'error': error,
            'services': services,
            'cupon': cupon,
            'customer': customer
        })

@permission_required('is_staff', 'adm:no-permission')
def CuponRedeemEndView(request):
    if request.method == 'POST':
        customer = request.POST.get('customer')
        try:
            sale = Sales.cupon_sale(request)
            if sale[0] == True:
                customer = User.objects.get(pk=customer)
                return Sales.render_view(request, customer)
        except CouponRedeemError as exc:
            customer = User.objects.get(pk=customer)
            return Sales.render_view(request, customer, message=str(exc))

class ReceivableView(UserAccessMixin, ListView):
    permission_required = 'is_staff'
    model = Sale
    template_name = "adm/receivable.html"
    paginate_by = 100  # Reduce la cantidad de objetos por página para mejorar la carga
    def get_queryset(self):
        from datetime import datetime as dt
        # Optimización: select_related y prefetch_related para evitar consultas N+1
        qs = Sale.objects.select_related(
            'account', 'customer', 'account__account_name'
        ).prefetch_related(
            'account__account_name__account_set'
        )
        if self.request.GET.get('date') is not None:
            # Convierte la fecha a datetime con zona horaria
            date_str = self.request.GET.get('date')
            start_date = timezone.make_aware(dt.strptime(date_str, '%Y-%m-%d').replace(hour=0, minute=0, second=0))
            end_date = timezone.make_aware(dt.strptime(date_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59))
            qs = qs.filter(
                expiration_date__gte=start_date,
                expiration_date__lte=end_date,
                status=True
            ).order_by('-expiration_date', 'account')
        elif self.request.GET.get('email'):
            email = self.request.GET.get('email')
            if self.request.GET.get('date') is not None:
                exp_date = self.request.GET.get('date')
                start_date = timezone.make_aware(dt.strptime(exp_date, '%Y-%m-%d').replace(hour=0, minute=0, second=0))
                end_date = timezone.make_aware(dt.strptime(exp_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59))
                qs = qs.filter(
                    expiration_date__gte=start_date,
                    expiration_date__lte=end_date,
                    status=True
                ).order_by('-expiration_date', 'account')
        else:
            # Mostrar todas las cuentas vencidas hoy o en el pasado respetando la zona horaria
            today = timezone.now().date()
            end_of_day = timezone.make_aware(dt.combine(today, dt.max.time()))
            qs = qs.filter(
                expiration_date__lte=end_of_day,
                status=True
            ).order_by('-expiration_date', 'account__email')
        return qs
    def get_context_data(self, **kwargs):
        from datetime import datetime as dt
        context = super().get_context_data(**kwargs)
        context['tomorrow'] = timezone.now().date() + timedelta(days=1)
        # Contar todas las cuentas vencidas (hoy y en el pasado)
        today = timezone.now().date()
        end_of_day = timezone.make_aware(dt.combine(today, dt.max.time()))
        context['left'] = Sale.objects.filter(
            expiration_date__lte=end_of_day,
            status=True
        ).count()
        return context

@permission_required('is_staff', 'adm:no-permission')
def ReceivableCopyPass(request, sale_id):
    sale = Sale.objects.get(pk=sale_id)
    message = f'Buenas tardes amig@, le recuerdo que su cuenta  {sale.account.account_name} ya venció, para seguir utilizándola debe renovar. Por ser cliente frecuente tendrás un 10% de descuento si renuevas por 3 meses o más el día de hoy.'
    clipboard.copy(message)
    return redirect(reverse('adm:receivable'))

@permission_required('is_staff', 'adm:no-permission')
def QuickReleaseAccount(request, sale_id):
    """
    Libera una cuenta directamente sin entrar en la vista de edición
    """
    if request.method == 'POST':
        try:
            sale = Sale.objects.get(pk=sale_id)
            sale.status = False
            sale.save()
            
            # Desasociar la cuenta del cliente y suspender la cuenta
            account = sale.account
            account.customer = None
            # account.status = False
            account.modified_by = request.user
            account.save()
            
            # Enviar notificación WhatsApp al cliente
            message = f'Le informamos que su cuenta {account.account_name.description} con email {account.email} fue suspendida por falta de pago. Aún está a tiempo de recuperarla renovando su cuenta. Por favor, si tiene alguna duda o comentario solo escribe Hablar con un Humano o envianos un whats app al número de siempre. Saludos.'
            customer_detail = UserDetail.objects.get(user=sale.customer)
            Notification.send_whatsapp_notification(message, customer_detail.lada, customer_detail.phone_number)
            
            # Si es AJAX, devolver JSON
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': 'Cuenta liberada exitosamente'})
            
            return redirect(reverse('adm:receivable'))
        except Exception as e:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': str(e)})
            return redirect(reverse('adm:receivable'))
    
    return JsonResponse({'success': False, 'message': 'Método no permitido'})

@permission_required('is_staff', 'adm:no-permission')
def ReleaseAccounts(request, pk):
    template_name = 'adm/accounts_create.html'
    success_url = reverse('adm:receivable')
    sale = Sale.objects.get(pk=pk)
    sale_email = sale.account.email
    sale_password = sale.account.password
    sale_account_mame_id = sale.account.account_name.id
    acc_list = Account.objects.filter(
        email=sale_email,
        password=sale_password,
        account_name=sale_account_mame_id
    )
    related_accounts = acc_list

    # AJAX para suspender/reactivar todas
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest' and request.GET.get('toggle_all'):
        # Determinar si todas están activas o no
        all_active = all(acc.status for acc in related_accounts)
        # Cambiar el estado de todas
        for acc in related_accounts:
            acc.status = not all_active
            acc.save()
        # Devolver el nuevo estado de cada cuenta
        return JsonResponse({
            'success': True,
            'all_active': not all_active,
            'related_accounts': [
                {
                    'id': acc.id,
                    'email': acc.email,
                    'profile': acc.profile,
                    'status': acc.status,
                    'expiration_date': acc.expiration_date.strftime('%d-%m-%Y') if acc.expiration_date else ''
                } for acc in related_accounts
            ]
        })

    # Lógica original (formulario normal)
    sales_to_release = []
    sales_to_report = []
    for acc in acc_list:
        now_aware = timezone.localtime(timezone.now()).replace(hour=23, minute=59, second=59, microsecond=999999)
        data_release = Sale.objects.filter(account=acc, status=True, expiration_date__lte=now_aware)
        data_report = Sale.objects.filter(account=acc, status=True, expiration_date__gte=now_aware)
        if data_release:
            sales_to_release.append(data_release)
        if data_report:
            sales_to_report.append(data_report)
    for sales in sales_to_release:
        sales[0].status = False
        sales[0].save()
        try:
            message = f'Le informamos que su cuenta {sales[0].account.account_name.description} con email {sales[0].account.email} fue suspendida por falta de pago. Aún está a tiempo de recuperarla renovando su cuenta. Por favor, si tiene alguna duda o comentario solo escribe Hablar con un Humano o envianos un whats app al número de siempre. Saludos.'
            customer_detail_released = UserDetail.objects.get(user=sales[0].customer)
            Notification.send_whatsapp_notification(message, customer_detail_released.lada, customer_detail_released.phone_number)
        except:
            pass
        account = sales[0].account
        account.customer = None
        account.modified_by = request.user
        account.save()
    data_account = sale.account
    form_class = AccountsForm(request.POST or None, instance=data_account)
    if request.method == 'POST':
        supplier = Supplier.objects.get(pk=request.POST.get('supplier'))
        modified_by = User.objects.get(pk=request.POST.get('modified_by'))
        account_name = Service.objects.get(pk=request.POST.get('account_name'))
        expiration_date = request.POST.get('expiration_date')
        email = request.POST.get('email')
        password = request.POST.get('password')
        comments = request.POST.get('comments')
        if request.POST.get('renovable') == 'on':
            renovable = True
        else:
            renovable = False
        old = Account.objects.get(pk=data_account.id)
        # Guardar la contraseña anterior para comparar
        old_password = old.password
        acc = Account.objects.filter(
            account_name=old.account_name,
            email=old.email
        )
        # Verificar si la contraseña cambió
        password_changed = old_password != password

        # Notificar a los clientes solo si cambió la contraseña (en segundo plano)
        if password_changed:
            webhook_url = os.environ.get("N8N_WEBHOOK_URL_CHANGE_PASSWORD")
            # Ejecutar notificaciones en un thread de fondo para no bloquear
            thread = Thread(
                target=_send_notifications_background,
                args=(sales_to_report, email, password, data_account, webhook_url),
                daemon=True
            )
            thread.start()

        # Usar bulk_update para actualizar todas las cuentas de una vez (mucho más rápido)
        if acc.exists():
            for a in acc:
                a.supplier = supplier
                a.modified_by = modified_by
                a.account_name = account_name
                a.expiration_date = expiration_date
                a.email = email
                a.password = password
                a.comments = comments
                a.renovable = renovable
            acc.model.objects.bulk_update(acc, [
                'supplier', 'modified_by', 'account_name', 'expiration_date', 
                'email', 'password', 'comments', 'renovable'
            ], batch_size=100)
        return redirect(success_url)
    return render(request, template_name, {
        'form': form_class,
        'related_accounts': related_accounts
    })

@permission_required('is_staff', 'adm:no-permission')
def credits(request, pk):
    template_name = 'adm/credits.html'
    customer = User.objects.get(pk=pk)
    success_url = reverse_lazy('adm:credit_list')
    if request.method == 'POST':
        credits = int(request.POST.get('credits'))
        if credits > 0:
            detail = "Recarga creditos"
        elif credits < 0:
            detail = "Ajuste manual de creditos"
        else:
            detail = "No hay cambios"
        op = Credits.objects.create(
            customer=customer, credits=credits, detail=detail)
        return redirect(success_url)
    return render(request, template_name, {
        'customer': customer
    })

@permission_required('is_staff', 'adm:no-permission')
def CreditsView(request):
    template_name = "adm/credits_list.html"
    customer = Credits.objects.values(
        'customer__username', 'customer').annotate(suma=Sum('credits'))
    return render(request, template_name, {
        'object_list': customer})

class CreditCustomerListView(UserAccessMixin, ListView):
    permission_required = 'is_staff'
    model = Credits
    template_name = "adm/credit_customer_list.html"
    paginate_by = 10
    ordering = ['-id']
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['customer'] = User.objects.get(pk=self.kwargs.get('pk'))
        return context

# def ImportView(request):

@permission_required('is_staff', 'adm:no-permission')
def ActiveInactiveAccount(request, status, pk):
    account = Account.objects.get(pk=pk)
    # Invertir el estado actual de la cuenta
    new_status = not account.status
    
    # Actualizar solo la cuenta específica seleccionada
    account.status = new_status
    account.save()

    # Verificar si es una petición AJAX
    is_ajax = request.headers.get('x-requested-with', '').lower() == 'xmlhttprequest'
    if is_ajax:
        # Respuesta para AJAX
        return JsonResponse({'success': True, 'new_status': new_status})
    return redirect(reverse('adm:accounts'))


@permission_required('is_staff', 'adm:no-permission')
def UpdateExternalStatusAccount(request, pk):
    if request.method != 'POST':
        return redirect(reverse('adm:accounts'))

    account = Account.objects.filter(pk=pk).first()
    if not account:
        is_ajax = request.headers.get('x-requested-with', '').lower() == 'xmlhttprequest'
        if is_ajax:
            return JsonResponse({'success': False, 'message': 'Cuenta no encontrada'}, status=404)
        return redirect(reverse('adm:accounts'))

    new_external_status = request.POST.get('external_status', '')
    available_statuses = [choice[0] for choice in Account._meta.get_field('external_status').choices]
    is_ajax = request.headers.get('x-requested-with', '').lower() == 'xmlhttprequest'

    if new_external_status in available_statuses:
        account.external_status = new_external_status
        account.save(update_fields=['external_status'])
        if is_ajax:
            return JsonResponse({'success': True, 'new_external_status': new_external_status})
    elif is_ajax:
        return JsonResponse({'success': False, 'message': 'Estado externo inválido'}, status=400)

    return redirect(request.META.get('HTTP_REFERER', reverse('adm:accounts')))
#     # ImportData.invoices()
#     # ImportData.update_country()
#     ImportData.shop()
#     ImportData.cupon()
#     return redirect(reverse('adm:index'))

@permission_required('is_staff', 'adm:no-permission')
def SearchRenewAcc(request, **kwargs):
    template_name = 'adm/search_renew_acc.html'
    account_name = Service.objects.filter(status=True)
    if request.method == 'GET':
        filters = {}
        for key, value in request.GET.items():
            if value == None or value == '' or value == {}:
                continue
            else:
                if value == 'on':
                    value = True
                filters[key] = value
        if len(filters) == 0:
            accounts = Account.objects.filter(
                renewal_date__lte=timezone.now().date(), renovable=True).annotate(
                time_diff=ExpressionWrapper(
    F('renewal_date') - timezone.now(), output_field=DurationField()
)
            ).order_by('time_diff')
        else:
            accounts = Account.objects.filter(
                **filters).annotate(
                time_diff=ExpressionWrapper(
                    F('renewal_date') - timezone.now(), output_field=DateTimeField())
            ).order_by('time_diff')
        return render(request, template_name, {
            'object_list': accounts,
            'account_name': account_name,
            'count': len(accounts)
        })

def setRenewalDateToExpirationDate(request):
    accounts = Account.objects.all()
    for account in accounts:
        account.renewal_date = account.expiration_date
        account.save()
    return redirect(reverse('adm:SearchRenewAcc'))

def toogleStatusRenewal(request, id):
    account = Account.objects.get(pk=id)
    account.status = not account.status
    account.save()
    return redirect(reverse('adm:SearchRenewAcc'))

def toogleRenewRenewal(request, id):
    account = Account.objects.get(pk=id)
    account.renovable = not account.renovable
    account.save()
    return redirect(reverse('adm:SearchRenewAcc'))


@csrf_exempt
@permission_required('is_staff', 'adm:no-permission')
def ToggleAccountStatus(request):
    """
    Suspender/Reactivar una cuenta vía AJAX
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            account_id = int(data.get('account_id'))
            
            account = Account.objects.get(pk=account_id)
            new_status = not account.status
            
            account.status = new_status
            account.modified_by = request.user
            account.save()
            
            status_text = 'Activa' if new_status else 'Suspendida'
            return JsonResponse({
                'success': True, 
                'message': f'Cuenta {status_text} exitosamente',
                'new_status': new_status
            })
        except Account.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Cuenta no encontrada'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False, 'message': 'Método no permitido'})


# Scripts

def duplicate_account(request):
    account_name = Service.objects.get(id=21)
    # Search account to duplicate
    accounts = Account.objects.filter(account_name=account_name, status=True, expiration_date__gte=timezone.now())
    for account in accounts:
        print(account)
    return HttpResponse("listo")


# Gestión de Imágenes del Index

@permission_required('is_staff', 'adm:no-permission')
def IndexImagesView(request):
    """Vista principal para gestionar imágenes del index"""
    from .models import IndexCarouselImage, IndexPromoImage

    template_name = 'adm/index_images.html'
    carousel_images = IndexCarouselImage.objects.all().order_by('order', '-created_at')
    promo_images = IndexPromoImage.objects.all().order_by('position', '-created_at')

    return render(request, template_name, {
        'carousel_images': carousel_images,
        'promo_images': promo_images
    })


class CarouselImageCreateView(UserAccessMixin, CreateView):
    """Crear nueva imagen de carrusel"""
    from .models import IndexCarouselImage
    from .functions.forms import IndexCarouselImageForm

    permission_required = 'is_staff'
    model = IndexCarouselImage
    form_class = IndexCarouselImageForm
    template_name = 'adm/carousel_image_form.html'
    success_url = reverse_lazy('adm:index_images')


class CarouselImageUpdateView(UserAccessMixin, UpdateView):
    """Actualizar imagen de carrusel"""
    from .models import IndexCarouselImage
    from .functions.forms import IndexCarouselImageForm

    permission_required = 'is_staff'
    model = IndexCarouselImage
    form_class = IndexCarouselImageForm
    template_name = 'adm/carousel_image_form.html'
    success_url = reverse_lazy('adm:index_images')


class CarouselImageDeleteView(UserAccessMixin, DeleteView):
    """Eliminar imagen de carrusel"""
    from .models import IndexCarouselImage

    permission_required = 'is_staff'
    model = IndexCarouselImage
    template_name = 'adm/delete.html'
    success_url = reverse_lazy('adm:index_images')


class PromoImageCreateView(UserAccessMixin, CreateView):
    """Crear nueva imagen de promoción"""
    from .models import IndexPromoImage
    from .functions.forms import IndexPromoImageForm

    permission_required = 'is_staff'
    model = IndexPromoImage
    form_class = IndexPromoImageForm
    template_name = 'adm/promo_image_form.html'
    success_url = reverse_lazy('adm:index_images')


class PromoImageUpdateView(UserAccessMixin, UpdateView):
    """Actualizar imagen de promoción"""
    from .models import IndexPromoImage
    from .functions.forms import IndexPromoImageForm

    permission_required = 'is_staff'
    model = IndexPromoImage
    form_class = IndexPromoImageForm
    template_name = 'adm/promo_image_form.html'
    success_url = reverse_lazy('adm:index_images')


class PromoImageDeleteView(UserAccessMixin, DeleteView):
    """Eliminar imagen de promoción"""
    from .models import IndexPromoImage

    permission_required = 'is_staff'
    model = IndexPromoImage
    template_name = 'adm/delete.html'
    success_url = reverse_lazy('adm:index_images')


@permission_required('is_staff', 'adm:no-permission')
def ToggleCarouselImageStatus(request, pk):
    """Activar/desactivar imagen del carrusel"""
    from .models import IndexCarouselImage

    image = IndexCarouselImage.objects.get(pk=pk)
    image.active = not image.active
    image.save()
    return redirect(reverse('adm:index_images'))


@permission_required('is_staff', 'adm:no-permission')
def TogglePromoImageStatus(request, pk):
    """Activar/desactivar imagen de promoción"""
    from .models import IndexPromoImage

    image = IndexPromoImage.objects.get(pk=pk)
    image.active = not image.active
    image.save()
    return redirect(reverse('adm:index_images'))


@csrf_exempt
@permission_required('is_staff', 'adm:no-permission')
def update_service_price(request):
    """
    Actualizar el precio de un servicio vía AJAX
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            service_id = data.get('service_id')
            field = data.get('field')  # 'price' o 'regular_price'
            value = data.get('value')

            if not all([service_id, field, value is not None]):
                return JsonResponse({'success': False, 'message': 'Datos incompletos'})

            if field not in ['price', 'regular_price']:
                return JsonResponse({'success': False, 'message': 'Campo inválido'})

            service = Service.objects.get(id=service_id)

            if field == 'price':
                service.price = int(value)
            elif field == 'regular_price':
                service.regular_price = int(value)

            service.save()

            return JsonResponse({'success': True, 'message': 'Actualizado correctamente'})

        except Service.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Servicio no encontrado'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})

    return JsonResponse({'success': False, 'message': 'Método no permitido'})


# ============================
# GESTIÓN DE PROMOCIONES
# ============================

@permission_required('is_staff', 'adm:no-permission')
def PromocionesView(request):
    """Vista principal para listar todas las promociones"""
    template_name = 'adm/promociones.html'
    promociones = Promocion.objects.all().order_by('-created_at')

    # Filtros
    search = request.GET.get('search', '')
    status_filter = request.GET.get('status_filter', '')
    tipo_filter = request.GET.get('tipo_filter', '')

    if search:
        promociones = promociones.filter(
            Q(nombre__icontains=search) | Q(descripcion__icontains=search)
        )

    if status_filter:
        promociones = promociones.filter(status=status_filter)

    if tipo_filter:
        promociones = promociones.filter(tipo_descuento=tipo_filter)

    return render(request, template_name, {
        'promociones': promociones,
        'search': search,
        'status_filter': status_filter,
        'tipo_filter': tipo_filter,
    })


@permission_required('is_staff', 'adm:no-permission')
def PromocionCreateView(request):
    """Crear nueva promoción"""
    from .functions.forms_promocion import PromocionForm
    template_name = 'adm/promocion_form.html'

    if request.method == 'POST':
        form = PromocionForm(request.POST, request.FILES)
        if form.is_valid():
            promocion = form.save(commit=False)
            promocion.created_by = request.user
            promocion.save()
            form.save_m2m()  # Guardar relaciones ManyToMany
            return redirect(reverse('adm:promociones'))
    else:
        form = PromocionForm()

    return render(request, template_name, {
        'form': form,
        'title': 'Crear Promoción'
    })


@permission_required('is_staff', 'adm:no-permission')
def PromocionUpdateView(request, pk):
    """Actualizar promoción existente"""
    from .functions.forms_promocion import PromocionForm
    template_name = 'adm/promocion_form.html'
    promocion = Promocion.objects.get(pk=pk)

    if request.method == 'POST':
        form = PromocionForm(request.POST, request.FILES, instance=promocion)
        if form.is_valid():
            form.save()
            return redirect(reverse('adm:promociones'))
    else:
        form = PromocionForm(instance=promocion)

    return render(request, template_name, {
        'form': form,
        'promocion': promocion,
        'title': 'Editar Promoción'
    })


@permission_required('is_staff', 'adm:no-permission')
def PromocionDeleteView(request, pk):
    """Eliminar promoción"""
    template_name = 'adm/delete.html'
    promocion = Promocion.objects.get(pk=pk)

    if request.method == 'POST':
        promocion.delete()
        return redirect(reverse('adm:promociones'))

    return render(request, template_name, {
        'object': promocion
    })


@permission_required('is_staff', 'adm:no-permission')
def PromocionToggleStatusView(request, pk):
    """Activar/Desactivar promoción"""
    promocion = Promocion.objects.get(pk=pk)

    # Antes de activar, verificar que no haya solapamiento
    if promocion.status != 'activa':
        tiene_solapamiento, promocion_conflictiva = Promocion.verificar_solapamiento(
            promocion.fecha_inicio,
            promocion.fecha_fin,
            excluir_id=pk
        )

        if tiene_solapamiento:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': f'No se puede activar. Ya existe una promoción activa: "{promocion_conflictiva.nombre}"'
                })
            else:
                # Redirigir con mensaje de error
                return redirect(reverse('adm:promociones'))

    if promocion.status == 'activa':
        promocion.status = 'inactiva'
    else:
        promocion.status = 'activa'

    promocion.save()

    # Si es AJAX, devolver JSON
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'new_status': promocion.status,
            'status_display': promocion.get_status_display()
        })

    return redirect(reverse('adm:promociones'))


@permission_required('is_staff', 'adm:no-permission')
def PromocionFechasDisponiblesView(request):
    """
    API endpoint para obtener recomendación de fechas disponibles
    """
    duracion_dias = request.GET.get('duracion_dias', None)
    excluir_id = request.GET.get('excluir_id', None)

    if duracion_dias:
        try:
            duracion_dias = int(duracion_dias)
        except ValueError:
            duracion_dias = None

    if excluir_id:
        try:
            excluir_id = int(excluir_id)
        except ValueError:
            excluir_id = None

    recomendacion = Promocion.recomendar_proxima_fecha(duracion_dias, excluir_id)

    # Formatear fechas para JSON
    response_data = {
        'puede_empezar_ahora': recomendacion.get('puede_empezar_ahora', False),
        'mensaje': recomendacion.get('mensaje', '')
    }

    if recomendacion.get('fecha_inicio'):
        # Formato para datetime-local input: YYYY-MM-DDTHH:MM
        response_data['fecha_inicio'] = recomendacion['fecha_inicio'].strftime('%Y-%m-%dT%H:%M')
        response_data['fecha_inicio_display'] = recomendacion['fecha_inicio'].strftime('%d/%m/%Y %H:%M')

    if recomendacion.get('fecha_fin'):
        response_data['fecha_fin'] = recomendacion['fecha_fin'].strftime('%Y-%m-%dT%H:%M')
        response_data['fecha_fin_display'] = recomendacion['fecha_fin'].strftime('%d/%m/%Y %H:%M')

    if recomendacion.get('ultima_promocion_termina'):
        response_data['ultima_promocion_termina'] = recomendacion['ultima_promocion_termina'].strftime('%d/%m/%Y %H:%M')

    return JsonResponse(response_data)


# ============================================
# VISTAS DE AFILIADOS - ADMIN
# ============================================

def AfiliadosListView(request):
    """Lista de afiliados con filtros"""
    template_name = "adm/afiliados/list.html"

    afiliados = Affiliate.objects.select_related('user', 'referido_por').all()

    # Filtros
    status = request.GET.get('status', '')
    search = request.GET.get('search', '')

    if status:
        afiliados = afiliados.filter(status=status)

    if search:
        afiliados = afiliados.filter(
            Q(user__username__icontains=search) |
            Q(user__email__icontains=search) |
            Q(codigo_afiliado__icontains=search) |
            Q(codigo_descuento__icontains=search)
        )

    # Estadisticas rapidas
    stats = {
        'total': Affiliate.objects.count(),
        'activos': Affiliate.objects.filter(status='activo').count(),
        'pendientes_comision': AffiliateCommission.objects.filter(status='pendiente').count(),
        'pendientes_retiro': AffiliateWithdrawal.objects.filter(status='pendiente').count(),
    }

    # Paginacion
    paginator = Paginator(afiliados, 25)
    page = request.GET.get('page', 1)
    afiliados_page = paginator.get_page(page)

    return render(request, template_name, {
        'afiliados': afiliados_page,
        'stats': stats,
        'status_filter': status,
        'search': search,
    })


def AfiliadosDetailView(request, pk):
    """Detalle de un afiliado"""
    template_name = "adm/afiliados/detail.html"

    try:
        affiliate = Affiliate.objects.select_related('user', 'referido_por').get(pk=pk)
    except Affiliate.DoesNotExist:
        from django.contrib import messages
        messages.error(request, 'Afiliado no encontrado')
        return redirect('adm:afiliados_list')

    # Ultimas ventas
    ultimas_ventas = affiliate.ventas.select_related('sale').order_by('-created_at')[:10]

    # Ultimas comisiones
    ultimas_comisiones = affiliate.comisiones.order_by('-created_at')[:10]

    # Ultimos retiros
    ultimos_retiros = affiliate.retiros.order_by('-created_at')[:10]

    # Referidos
    referidos = affiliate.referidos.all()[:10]

    # Estadisticas
    from django.db.models import Sum, Count
    stats = {
        'total_ventas': affiliate.ventas.count(),
        'monto_ventas': affiliate.ventas.aggregate(
            total=Sum('sale__payment_amount')
        )['total'] or 0,
        'comisiones_aprobadas': affiliate.comisiones.filter(
            status='aprobada'
        ).aggregate(total=Sum('monto'))['total'] or 0,
        'comisiones_pendientes': affiliate.comisiones.filter(
            status='pendiente'
        ).aggregate(total=Sum('monto'))['total'] or 0,
        'total_retirado': affiliate.retiros.filter(
            status='completado'
        ).aggregate(total=Sum('monto'))['total'] or 0,
        'total_referidos': affiliate.referidos.count(),
    }

    return render(request, template_name, {
        'affiliate': affiliate,
        'ultimas_ventas': ultimas_ventas,
        'ultimas_comisiones': ultimas_comisiones,
        'ultimos_retiros': ultimos_retiros,
        'referidos': referidos,
        'stats': stats,
    })


def AfiliadosToggleStatus(request, pk):
    """Activa/desactiva un afiliado"""
    from django.contrib import messages

    try:
        affiliate = Affiliate.objects.get(pk=pk)
        if affiliate.status == 'activo':
            affiliate.status = 'suspendido'
            messages.success(request, f'Afiliado {affiliate.codigo_afiliado} suspendido.')
        else:
            affiliate.status = 'activo'
            messages.success(request, f'Afiliado {affiliate.codigo_afiliado} activado.')
        affiliate.save()
    except Affiliate.DoesNotExist:
        messages.error(request, 'Afiliado no encontrado')

    return redirect('adm:afiliados_detail', pk=pk)


def AfiliadosToggleAutoComision(request, pk):
    """Activa/desactiva comisiones automaticas para un afiliado"""
    from django.contrib import messages

    try:
        affiliate = Affiliate.objects.get(pk=pk)
        affiliate.comision_automatica = not affiliate.comision_automatica
        affiliate.save()
        if affiliate.comision_automatica:
            messages.success(request, f'Comisiones automaticas activadas para {affiliate.codigo_afiliado}.')
        else:
            messages.info(request, f'Comisiones automaticas desactivadas para {affiliate.codigo_afiliado}.')
    except Affiliate.DoesNotExist:
        messages.error(request, 'Afiliado no encontrado')

    return redirect('adm:afiliados_detail', pk=pk)


def AfiliadosConfigView(request):
    """Configuracion global del sistema de afiliados"""
    template_name = "adm/afiliados/config.html"
    from django.contrib import messages

    settings_aff = AffiliateSettings.get_settings()

    if request.method == 'POST':
        try:
            settings_aff.comision_monto = float(request.POST.get('comision_monto', 50))
            settings_aff.porcentaje_descuento_default = float(request.POST.get('porcentaje_descuento_default', 5))
            settings_aff.minimo_retiro = float(request.POST.get('minimo_retiro', 500))
            settings_aff.porcentaje_comision_referido = float(request.POST.get('porcentaje_comision_referido', 10))
            settings_aff.email_soporte = request.POST.get('email_soporte', '')
            settings_aff.whatsapp_soporte = request.POST.get('whatsapp_soporte', '')
            settings_aff.umbral_soporte_premium = float(request.POST.get('umbral_soporte_premium', 5000))
            settings_aff.url_terminos = request.POST.get('url_terminos', '')
            settings_aff.save()
            messages.success(request, 'Configuracion guardada correctamente.')
        except Exception as e:
            messages.error(request, f'Error guardando configuracion: {str(e)}')

    return render(request, template_name, {
        'settings': settings_aff,
        'total_afiliados': Affiliate.objects.filter(status='activo').count(),
    })


def AfiliadosUpdateDescuento(request, pk):
    """Actualiza el descuento de un afiliado individual"""
    from django.contrib import messages

    if request.method == 'POST':
        try:
            affiliate = Affiliate.objects.get(pk=pk)
            nuevo_descuento = float(request.POST.get('porcentaje_descuento', 0))

            if 0 <= nuevo_descuento <= 100:
                affiliate.porcentaje_descuento = nuevo_descuento
                affiliate.save()
                messages.success(request, f'Descuento actualizado a {nuevo_descuento}% para {affiliate.codigo_afiliado}.')
            else:
                messages.error(request, 'El descuento debe estar entre 0 y 100.')
        except Affiliate.DoesNotExist:
            messages.error(request, 'Afiliado no encontrado.')
        except ValueError:
            messages.error(request, 'Valor de descuento invalido.')

    return redirect('adm:afiliados_detail', pk=pk)


def AfiliadosDescuentoMasivo(request):
    """Actualiza el descuento de todos los afiliados activos"""
    from django.contrib import messages

    if request.method == 'POST':
        try:
            nuevo_descuento = float(request.POST.get('nuevo_descuento', 0))

            if 0 <= nuevo_descuento <= 100:
                afiliados_actualizados = Affiliate.objects.filter(status='activo').update(
                    porcentaje_descuento=nuevo_descuento
                )
                messages.success(
                    request,
                    f'Descuento actualizado a {nuevo_descuento}% para {afiliados_actualizados} afiliados.'
                )
            else:
                messages.error(request, 'El descuento debe estar entre 0 y 100.')
        except ValueError:
            messages.error(request, 'Valor de descuento invalido.')

    return redirect('adm:afiliados_config')


def AfiliadosComisionesListView(request):
    """Lista de comisiones para gestion"""
    template_name = "adm/afiliados/comisiones.html"

    comisiones = AffiliateCommission.objects.select_related(
        'affiliate__user', 'affiliate_sale__sale'
    ).order_by('-created_at')

    # Filtros
    status = request.GET.get('status', 'pendiente')
    if status:
        comisiones = comisiones.filter(status=status)

    # Paginacion
    paginator = Paginator(comisiones, 50)
    page = request.GET.get('page', 1)
    comisiones_page = paginator.get_page(page)

    # Stats
    stats = {
        'pendientes': AffiliateCommission.objects.filter(status='pendiente').count(),
        'monto_pendiente': AffiliateCommission.objects.filter(
            status='pendiente'
        ).aggregate(total=Sum('monto'))['total'] or 0,
    }

    return render(request, template_name, {
        'comisiones': comisiones_page,
        'stats': stats,
        'status_filter': status,
    })


def AfiliadosComisionAprobar(request, pk):
    """Aprueba una comision pendiente"""
    from django.contrib import messages
    from index.utils_affiliates import crear_notificacion_afiliado

    try:
        comision = AffiliateCommission.objects.get(pk=pk)
        if comision.status == 'pendiente':
            comision.aprobar()
            messages.success(request, f'Comision #{pk} aprobada.')
            # Notificar al afiliado
            crear_notificacion_afiliado(
                comision.affiliate,
                'comision',
                'Comision Aprobada',
                f'Tu comision de ${comision.monto:.2f} MXN ha sido aprobada.',
                '/afiliados/comisiones/'
            )
        else:
            messages.warning(request, f'La comision #{pk} no esta pendiente.')
    except AffiliateCommission.DoesNotExist:
        messages.error(request, 'Comision no encontrada')

    return redirect('adm:afiliados_comisiones_admin')


def AfiliadosComisionRechazar(request, pk):
    """Rechaza una comision"""
    from django.contrib import messages
    from index.utils_affiliates import crear_notificacion_afiliado

    try:
        comision = AffiliateCommission.objects.get(pk=pk)
        if comision.status == 'pendiente':
            motivo = request.POST.get('motivo', 'Rechazada por admin')
            comision.rechazar(motivo)
            messages.success(request, f'Comision #{pk} rechazada.')
            # Notificar al afiliado
            crear_notificacion_afiliado(
                comision.affiliate,
                'comision_rechazada',
                'Comision Rechazada',
                f'Tu comision de ${comision.monto:.2f} MXN ha sido rechazada. Motivo: {motivo}',
                '/afiliados/comisiones/'
            )
        else:
            messages.warning(request, f'La comision #{pk} no esta pendiente.')
    except AffiliateCommission.DoesNotExist:
        messages.error(request, 'Comision no encontrada')

    return redirect('adm:afiliados_comisiones_admin')


def AfiliadosRetirosListView(request):
    """Lista de retiros para gestion"""
    template_name = "adm/afiliados/retiros.html"

    retiros = AffiliateWithdrawal.objects.select_related('affiliate__user').order_by('-created_at')

    # Filtros
    status = request.GET.get('status', 'pendiente')
    if status:
        retiros = retiros.filter(status=status)

    # Paginacion
    paginator = Paginator(retiros, 50)
    page = request.GET.get('page', 1)
    retiros_page = paginator.get_page(page)

    # Stats
    stats = {
        'pendientes': AffiliateWithdrawal.objects.filter(status='pendiente').count(),
        'monto_pendiente': AffiliateWithdrawal.objects.filter(
            status='pendiente'
        ).aggregate(total=Sum('monto'))['total'] or 0,
    }

    return render(request, template_name, {
        'retiros': retiros_page,
        'stats': stats,
        'status_filter': status,
    })


def AfiliadosRetiroAprobar(request, pk):
    """Aprueba un retiro pendiente"""
    from django.contrib import messages
    from index.utils_affiliates import crear_notificacion_afiliado

    try:
        retiro = AffiliateWithdrawal.objects.get(pk=pk)
        if retiro.status == 'pendiente':
            retiro.aprobar()
            messages.success(request, f'Retiro #{pk} aprobado y completado.')
            # Notificar al afiliado
            crear_notificacion_afiliado(
                retiro.affiliate,
                'retiro',
                'Retiro Procesado',
                f'Tu retiro de ${retiro.monto:.2f} MXN ha sido procesado.',
                '/afiliados/retiros/'
            )
        else:
            messages.warning(request, f'El retiro #{pk} no esta pendiente.')
    except AffiliateWithdrawal.DoesNotExist:
        messages.error(request, 'Retiro no encontrado')

    return redirect('adm:afiliados_retiros_admin')


def AfiliadosRetiroRechazar(request, pk):
    """Rechaza un retiro"""
    from django.contrib import messages
    from index.utils_affiliates import crear_notificacion_afiliado

    try:
        retiro = AffiliateWithdrawal.objects.get(pk=pk)
        if retiro.status == 'pendiente':
            motivo = request.POST.get('motivo', 'Rechazado por admin')
            retiro.rechazar(motivo)
            messages.success(request, f'Retiro #{pk} rechazado.')
            # Notificar al afiliado
            crear_notificacion_afiliado(
                retiro.affiliate,
                'retiro_rechazado',
                'Retiro Rechazado',
                f'Tu retiro de ${retiro.monto:.2f} MXN ha sido rechazado. Motivo: {motivo}',
                '/afiliados/retiros/'
            )
        else:
            messages.warning(request, f'El retiro #{pk} no esta pendiente.')
    except AffiliateWithdrawal.DoesNotExist:
        messages.error(request, 'Retiro no encontrado')

    return redirect('adm:afiliados_retiros_admin')


def AfiliadosStatsView(request):
    """Dashboard de estadisticas de afiliados"""
    template_name = "adm/afiliados/stats.html"

    from django.db.models import Count
    from django.db.models.functions import TruncMonth, TruncDate

    now = timezone.now()
    inicio_mes = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Estadisticas generales
    stats = {
        'total_afiliados': Affiliate.objects.count(),
        'afiliados_activos': Affiliate.objects.filter(status='activo').count(),
        'ventas_mes': AffiliateSale.objects.filter(created_at__gte=inicio_mes).count(),
        'monto_ventas_mes': AffiliateSale.objects.filter(
            created_at__gte=inicio_mes
        ).aggregate(total=Sum('sale__payment_amount'))['total'] or 0,
        'comisiones_mes': AffiliateCommission.objects.filter(
            created_at__gte=inicio_mes
        ).aggregate(total=Sum('monto'))['total'] or 0,
        'comisiones_pendientes': AffiliateCommission.objects.filter(
            status='pendiente'
        ).aggregate(total=Sum('monto'))['total'] or 0,
        'retiros_pendientes': AffiliateWithdrawal.objects.filter(
            status='pendiente'
        ).aggregate(total=Sum('monto'))['total'] or 0,
    }

    # Top afiliados del mes
    top_afiliados = Affiliate.objects.filter(
        ventas__created_at__gte=inicio_mes
    ).annotate(
        ventas_count=Count('ventas')
    ).order_by('-ventas_count')[:10]

    # Ventas por dia (ultimos 30 dias)
    ventas_por_dia = AffiliateSale.objects.filter(
        created_at__gte=now - timedelta(days=30)
    ).annotate(
        fecha=TruncDate('created_at')
    ).values('fecha').annotate(
        cantidad=Count('id'),
        monto=Sum('sale__payment_amount')
    ).order_by('fecha')

    return render(request, template_name, {
        'stats': stats,
        'top_afiliados': top_afiliados,
        'ventas_por_dia': list(ventas_por_dia),
    })


# ============================================================================
# LOGS DE SINCRONIZACIÓN DE GOOGLE SHEETS
# ============================================================================

@login_required
def sync_logs_view(request):
    """
    Vista para ver los logs de sincronización de Google Sheets.
    Ubicación: /adm/sync-logs/
    Filtros: por fecha (desde/hasta)
    """
    from pathlib import Path
    from datetime import datetime, date
    
    log_file_path = Path(os.path.dirname(os.path.dirname(__file__))) / "logs" / "sync_sheets.log"
    
    # Obtener filtros de fecha del request
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # Parámetros de paginación
    lines_per_page = 100
    page = request.GET.get('page', 1)
    
    all_lines = []
    
    if log_file_path.exists():
        try:
            with open(log_file_path, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
                
                # Filtrar por fecha si se proporcionan
                if date_from or date_to:
                    filtered_lines = []
                    for line in all_lines:
                        try:
                            # Extraer timestamp del log (formato: [YYYY-MM-DDTHH:MM:SS...]
                            if '[' in line and ']' in line:
                                timestamp_str = line.split(']')[0].strip('[')
                                # Parsear la fecha (tomar solo la parte YYYY-MM-DD)
                                log_date = timestamp_str.split('T')[0]  # YYYY-MM-DD
                                
                                # Comparar fechas
                                include = True
                                if date_from:
                                    include = include and log_date >= date_from
                                if date_to:
                                    include = include and log_date <= date_to
                                
                                if include:
                                    filtered_lines.append(line)
                        except:
                            # Si no se puede parsear la fecha, incluir la línea
                            filtered_lines.append(line)
                    all_lines = filtered_lines
                
                # Invertir para mostrar los más recientes primero
                all_lines = list(reversed(all_lines))
        except Exception as e:
            all_lines = [f"❌ Error leyendo logs: {str(e)}"]
    
    # Paginar
    paginator = Paginator(all_lines, lines_per_page)
    
    try:
        logs_page = paginator.page(page)
    except PageNotAnInteger:
        logs_page = paginator.page(1)
    except EmptyPage:
        logs_page = paginator.page(paginator.num_pages)
    
    # Colorear logs por tipo
    colorized_logs = []
    for line in logs_page:
        if "❌" in line:
            color_class = "log-error"
        elif "✅" in line:
            color_class = "log-success"
        elif "📱" in line or "📧" in line:
            color_class = "log-notification"
        elif "⚠️" in line:
            color_class = "log-warning"
        elif "✏️" in line:
            color_class = "log-update"
        elif "ℹ️" in line:
            color_class = "log-info"
        else:
            color_class = "log-default"
        
        colorized_logs.append({
            'text': line.rstrip(),
            'class': color_class
        })
    
    context = {
        'logs': colorized_logs,
        'paginator': paginator,
        'page_obj': logs_page,
        'total_lines': len(all_lines),
        'has_logs': len(all_lines) > 0,
        'date_from': date_from,
        'date_to': date_to,
    }
    
    return render(request, 'adm/sync_logs.html', context)


@login_required
def sync_logs_download(request):
    """
    Descargar archivo completo de logs.
    """
    from pathlib import Path
    
    log_file_path = Path(os.path.dirname(os.path.dirname(__file__))) / "logs" / "sync_sheets.log"
    
    if not log_file_path.exists():
        return JsonResponse({'error': 'No hay logs'}, status=404)
    
    with open(log_file_path, 'r', encoding='utf-8') as f:
        logs_content = f.read()
    
    response = HttpResponse(logs_content, content_type='text/plain; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="sync_sheets.log"'
    return response


@login_required
@csrf_exempt
def sync_logs_clear(request):
    """
    Limpiar los logs (solo para admin).
    """
    from pathlib import Path
    
    if not request.user.is_staff:
        return JsonResponse({'error': 'No tienes permiso'}, status=403)
    
    log_file_path = Path(os.path.dirname(os.path.dirname(__file__))) / "logs" / "sync_sheets.log"
    
    try:
        # Crear backup
        if log_file_path.exists():
            backup_path = log_file_path.parent / f"sync_sheets_backup_{timezone.now().strftime('%Y%m%d_%H%M%S')}.log"
            with open(log_file_path, 'r') as f:
                backup_content = f.read()
            with open(backup_path, 'w') as f:
                f.write(backup_content)
        
        # Limpiar
        with open(log_file_path, 'w') as f:
            f.write(f"[{timezone.now().isoformat()}] 🔄 Logs limpiados por {request.user.username}\n")
        
        return JsonResponse({
            'status': 'success',
            'message': 'Logs limpiados exitosamente'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@login_required
@csrf_exempt
def sync_google_sheets_execute(request):
    """
    Ejecuta la sincronización de Google Sheets desde el panel /adm.
    Solo para admin.
    """
    from django.core.management import call_command
    from io import StringIO
    
    if not request.user.is_staff:
        return JsonResponse({'error': 'No tienes permiso'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Solo POST permitido'}, status=405)
    
    try:
        # Ejecutar el comando de sincronización
        output = StringIO()
        call_command('sync_google_sheets', '--verbose', stdout=output)
        result = output.getvalue()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Sincronización completada',
            'result': result
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Error en sincronización: {str(e)}'
        }, status=500)


# ============================================================================
# MARKETING IA
# ============================================================================

def _marketing_stats_snapshot(user):
    now = timezone.now()
    last_90 = now - timedelta(days=90)
    qs = Sale.objects.filter(created_at__gte=last_90, status=True)
    if not user.is_superuser:
        qs = qs.filter(user_seller=user)

    totals = qs.aggregate(total_sales=Count('id'), total_revenue=Sum('payment_amount'))
    avg_ticket = 0
    if totals['total_sales']:
        avg_ticket = float(totals['total_revenue'] or 0) / float(totals['total_sales'])

    top_services = (
        qs.values('account__account_name__description')
        .annotate(total_revenue=Sum('payment_amount'), total_sales=Count('id'))
        .order_by('-total_revenue')[:5]
    )
    top_countries = (
        qs.values('customer__userdetail__country')
        .annotate(total_sales=Count('id'), total_revenue=Sum('payment_amount'))
        .order_by('-total_revenue')[:8]
    )
    return {
        'window_days': 90,
        'total_sales': int(totals['total_sales'] or 0),
        'total_revenue': float(totals['total_revenue'] or 0),
        'avg_ticket': round(avg_ticket, 2),
        'top_services': list(top_services),
        'top_countries': list(top_countries),
        'generated_at': timezone.now().isoformat(),
    }


def _marketing_parse_json(text):
    raw = (text or '').strip()
    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)
    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        pass
    start = raw.find('{')
    end = raw.rfind('}')
    if start >= 0 and end > start:
        try:
            obj = json.loads(raw[start:end + 1])
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}
    return {}


def _mysql_safe_text(value):
    """
    Evita errores 'Incorrect string value' en MySQL utf8 (3 bytes),
    removiendo caracteres fuera de BMP (ej: muchos emojis).
    """
    if value is None:
        return ''
    raw = str(value)
    cleaned = []
    for ch in raw:
        code = ord(ch)
        if code <= 0xFFFF:
            cleaned.append(ch)
    return ''.join(cleaned)


def _error_to_text(exc):
    base = _mysql_safe_text(str(exc))
    details = getattr(exc, 'details', None)
    if details:
        try:
            details_text = _mysql_safe_text(json.dumps(details, ensure_ascii=False, default=str))
            return f"{base} | details={details_text}"
        except Exception:
            pass
    return base


def _force_square_image_bytes(raw_bytes):
    """
    Garantiza salida 1:1 (cuadrada), recortando al centro.
    """
    if not raw_bytes or Image is None:
        return raw_bytes
    try:
        source = BytesIO(raw_bytes)
        with Image.open(source) as img:
            width, height = img.size
            side = min(width, height)
            left = (width - side) // 2
            top = (height - side) // 2
            cropped = img.crop((left, top, left + side, top + side))
            output = BytesIO()
            cropped.save(output, format='PNG')
            return output.getvalue()
    except Exception:
        return raw_bytes


def _marketing_db_context(user):
    """
    Contexto SQL (solo lectura) para decisiones de marketing:
    servicios activos, precios, ventas recientes, promociones y cupones.
    """
    cfg = get_db_mcp_config()
    mcp = ReadOnlyDatabaseMCP(
        allowed_tables=cfg["allowed_tables"] or None,
        max_rows=min(int(cfg["max_rows"]), 300),
        include_schema=False,
    )
    now = timezone.now()
    since_90 = now - timedelta(days=90)

    query_specs = []

    # Servicios activos + tracción últimos 90 días
    if user and not user.is_superuser:
        query_specs.append(
            (
                """
                SELECT
                  s.id,
                  s.description,
                  s.price,
                  s.regular_price,
                  COUNT(sa.id) AS sales_90d,
                  COALESCE(SUM(sa.payment_amount), 0) AS revenue_90d
                FROM adm_service s
                LEFT JOIN adm_account a ON a.account_name_id = s.id
                LEFT JOIN adm_sale sa
                  ON sa.account_id = a.id
                 AND sa.status = 1
                 AND sa.created_at >= %s
                 AND sa.user_seller_id = %s
                WHERE s.status = 1
                GROUP BY s.id, s.description, s.price, s.regular_price
                ORDER BY sales_90d DESC, revenue_90d DESC
                """,
                [since_90, user.id],
            )
        )
    else:
        query_specs.append(
            (
                """
                SELECT
                  s.id,
                  s.description,
                  s.price,
                  s.regular_price,
                  COUNT(sa.id) AS sales_90d,
                  COALESCE(SUM(sa.payment_amount), 0) AS revenue_90d
                FROM adm_service s
                LEFT JOIN adm_account a ON a.account_name_id = s.id
                LEFT JOIN adm_sale sa
                  ON sa.account_id = a.id
                 AND sa.status = 1
                 AND sa.created_at >= %s
                WHERE s.status = 1
                GROUP BY s.id, s.description, s.price, s.regular_price
                ORDER BY sales_90d DESC, revenue_90d DESC
                """,
                [since_90],
            )
        )

    # Promociones activas/programadas
    query_specs.append(
        (
            """
            SELECT
              id, nombre, tipo_descuento, porcentaje_descuento, monto_descuento,
              tipo_nxm, cantidad_llevar, cantidad_pagar, aplicacion, status,
              fecha_inicio, fecha_fin
            FROM adm_promocion
            WHERE status IN ('activa', 'programada')
            ORDER BY updated_at DESC
            """,
            [],
        )
    )

    # Cupones disponibles (potenciales "días de regalo")
    query_specs.append(
        (
            """
            SELECT
              id, name, status, duration_unit, duration_quantity, price,
              max_uses, used_count, (max_uses - used_count) AS remaining_uses,
              status_sale, status_payment
            FROM cupon_cupon
            WHERE status = 1
            ORDER BY remaining_uses DESC, id DESC
            """,
            [],
        )
    )

    # Rendimiento por país últimos 90 días
    if user and not user.is_superuser:
        query_specs.append(
            (
                """
                SELECT
                  COALESCE(ud.country, 'Sin país') AS country,
                  COUNT(sa.id) AS sales_90d,
                  COALESCE(SUM(sa.payment_amount), 0) AS revenue_90d
                FROM adm_sale sa
                JOIN auth_user u ON u.id = sa.customer_id
                LEFT JOIN adm_userdetail ud ON ud.user_id = u.id
                WHERE sa.status = 1
                  AND sa.created_at >= %s
                  AND sa.user_seller_id = %s
                GROUP BY COALESCE(ud.country, 'Sin país')
                ORDER BY revenue_90d DESC
                """,
                [since_90, user.id],
            )
        )
    else:
        query_specs.append(
            (
                """
                SELECT
                  COALESCE(ud.country, 'Sin país') AS country,
                  COUNT(sa.id) AS sales_90d,
                  COALESCE(SUM(sa.payment_amount), 0) AS revenue_90d
                FROM adm_sale sa
                JOIN auth_user u ON u.id = sa.customer_id
                LEFT JOIN adm_userdetail ud ON ud.user_id = u.id
                WHERE sa.status = 1
                  AND sa.created_at >= %s
                GROUP BY COALESCE(ud.country, 'Sin país')
                ORDER BY revenue_90d DESC
                """,
                [since_90],
            )
        )

    results = []
    errors = []
    for sql, params in query_specs:
        try:
            q = mcp.query(sql, params=params, limit=200)
            results.append(
                {
                    'sql': _mysql_safe_text(q.sql),
                    'row_count': q.row_count,
                    'rows': q.rows,
                }
            )
        except Exception as exc:
            errors.append(_mysql_safe_text(str(exc)))

    payload = {
        'generated_at': timezone.now().isoformat(),
        'query_results': results,
        'errors': errors,
    }
    if mcp.include_schema:
        try:
            payload['schema'] = mcp.get_schema_context()
        except Exception as exc:
            payload['schema_error'] = _mysql_safe_text(str(exc))
    return payload


def _extract_inactivity_days_threshold(*texts):
    merged = " ".join(str(t or "") for t in texts).lower()
    # Ejemplos: "45 días", "45dias", "mas de 45 dias"
    m = re.search(r"(\d{1,3})\s*d[ií]as", merged)
    if not m:
        m = re.search(r"(\d{1,3})dias", merged)
    if not m:
        return 45
    days = int(m.group(1))
    return max(7, min(days, 365))


def _campaign_text_blob(campaign):
    return " ".join(
        [
            str(campaign.name or ""),
            str(campaign.objective or ""),
            str(campaign.idea_input or ""),
            str(campaign.message_text or ""),
            str(campaign.sms_text or ""),
            " ".join(str(t or "") for t in (campaign.tags or [])),
        ]
    ).lower()


def _default_audience_strategy(campaign):
    blob = _campaign_text_blob(campaign)
    strategy = {
        'segment_type': 'general',
        'min_days_inactive': 0,
        'max_days_inactive': 3650,
        'require_no_active_sales': False,
        'require_target_service_inactive': False,
        'require_service_history': False,
        'exclude_recent_same_service_days': 2,
        'min_total_orders': 0,
        'max_total_orders': 9999,
        'min_total_revenue': 0,
        'max_active_sales_now': 999,
        'countries_include': [],
        'countries_exclude': [],
        'service_keywords': [],
        'notes': 'Estrategia base.',
        'source': 'heuristic',
    }
    if any(k in blob for k in ['reactiv', 'winback', 'volver', 'inactivo', 'sin comprar', 'recuper']):
        strategy.update(
            {
                'segment_type': 'reactivation',
                'min_days_inactive': _extract_inactivity_days_threshold(blob),
                'require_no_active_sales': True,
                'require_target_service_inactive': True,
                'require_service_history': True,
                'max_active_sales_now': 0,
                'notes': 'Reactivación: clientes inactivos con historial del servicio.',
            }
        )
    elif any(k in blob for k in ['upsell', 'upgrade', 'subir plan', 'ticket mayor']):
        strategy.update(
            {
                'segment_type': 'upsell',
                'min_days_inactive': 0,
                'max_days_inactive': 90,
                'min_total_orders': 1,
                'notes': 'Upsell: clientes activos o recientes con mayor propensión.',
            }
        )
    elif any(k in blob for k in ['cross', 'cruzada', 'complement', 'bundle']):
        strategy.update(
            {
                'segment_type': 'cross_sell',
                'min_days_inactive': 0,
                'max_days_inactive': 180,
                'min_total_orders': 1,
                'notes': 'Cross-sell: clientes compradores con potencial de servicios complementarios.',
            }
        )
    elif any(k in blob for k in ['premium', 'alto valor', 'vip']):
        strategy.update(
            {
                'segment_type': 'premium',
                'min_total_orders': 2,
                'min_total_revenue': 250,
                'max_days_inactive': 180,
                'notes': 'Premium: clientes de alto valor.',
            }
        )
    elif any(k in blob for k in ['retención', 'retencion', 'renov', 'evitar churn', 'churn']):
        strategy.update(
            {
                'segment_type': 'retention',
                'min_days_inactive': 0,
                'max_days_inactive': 45,
                'min_total_orders': 1,
                'notes': 'Retención: clientes recientes con riesgo de enfriarse.',
            }
        )
    return strategy


def _normalize_country_list(values):
    if not isinstance(values, list):
        return []
    cleaned = []
    for item in values:
        val = _mysql_safe_text(item).strip().lower()
        if val and val not in cleaned:
            cleaned.append(val)
    return cleaned[:20]


def _infer_audience_strategy(campaign):
    strategy = _default_audience_strategy(campaign)
    provider = get_active_provider()
    text_model = get_model_for_task('text', provider=provider)
    if not text_model:
        return strategy
    try:
        client = AIClient.from_settings(timeout=35)
        prompt = (
            "Eres estratega de segmentación de audiencias.\n"
            "Devuelve SOLO JSON con criterios para filtrar clientes congruentes al objetivo de campaña.\n"
            "JSON:\n"
            "{"
            "\"segment_type\":\"reactivation|upsell|cross_sell|retention|premium|acquisition|churn_risk|general\","
            "\"min_days_inactive\":0,"
            "\"max_days_inactive\":3650,"
            "\"require_no_active_sales\":false,"
            "\"require_target_service_inactive\":false,"
            "\"require_service_history\":false,"
            "\"exclude_recent_same_service_days\":2,"
            "\"min_total_orders\":0,"
            "\"max_total_orders\":9999,"
            "\"min_total_revenue\":0,"
            "\"max_active_sales_now\":999,"
            "\"countries_include\":[],"
            "\"countries_exclude\":[],"
            "\"service_keywords\":[],"
            "\"notes\":\"...\""
            "}\n\n"
            f"Campaña: {json.dumps({'name': campaign.name, 'objective': campaign.objective, 'idea_input': campaign.idea_input, 'message_text': campaign.message_text, 'sms_text': campaign.sms_text, 'tags': campaign.tags}, ensure_ascii=False, default=str)}\n"
            f"Estadísticas: {json.dumps(campaign.stats_snapshot or {}, ensure_ascii=False, default=str)}"
        )
        result = client.generate(
            model=text_model,
            prompt=prompt,
            system_prompt="Responde solo JSON válido.",
            temperature=0.15,
            max_output_tokens=500,
        )
        payload = _marketing_parse_json(result.text)
        if isinstance(payload, dict) and payload:
            strategy.update(
                {
                    'segment_type': _mysql_safe_text(payload.get('segment_type') or strategy['segment_type']).strip().lower(),
                    'min_days_inactive': int(payload.get('min_days_inactive', strategy['min_days_inactive'])),
                    'max_days_inactive': int(payload.get('max_days_inactive', strategy['max_days_inactive'])),
                    'require_no_active_sales': bool(payload.get('require_no_active_sales', strategy['require_no_active_sales'])),
                    'require_target_service_inactive': bool(payload.get('require_target_service_inactive', strategy['require_target_service_inactive'])),
                    'require_service_history': bool(payload.get('require_service_history', strategy['require_service_history'])),
                    'exclude_recent_same_service_days': int(payload.get('exclude_recent_same_service_days', strategy['exclude_recent_same_service_days'])),
                    'min_total_orders': int(payload.get('min_total_orders', strategy['min_total_orders'])),
                    'max_total_orders': int(payload.get('max_total_orders', strategy['max_total_orders'])),
                    'min_total_revenue': float(payload.get('min_total_revenue', strategy['min_total_revenue'])),
                    'max_active_sales_now': int(payload.get('max_active_sales_now', strategy['max_active_sales_now'])),
                    'countries_include': _normalize_country_list(payload.get('countries_include', [])),
                    'countries_exclude': _normalize_country_list(payload.get('countries_exclude', [])),
                    'service_keywords': [
                        _mysql_safe_text(v).strip().lower()
                        for v in (payload.get('service_keywords') or [])
                        if _mysql_safe_text(v).strip()
                    ][:20],
                    'notes': _mysql_safe_text(payload.get('notes', strategy['notes'])),
                    'source': 'ai',
                }
            )
    except Exception:
        pass
    strategy['min_days_inactive'] = max(0, min(int(strategy.get('min_days_inactive', 0)), 3650))
    strategy['max_days_inactive'] = max(strategy['min_days_inactive'], min(int(strategy.get('max_days_inactive', 3650)), 3650))
    strategy['exclude_recent_same_service_days'] = max(0, min(int(strategy.get('exclude_recent_same_service_days', 2)), 30))
    strategy['min_total_orders'] = max(0, min(int(strategy.get('min_total_orders', 0)), 10000))
    strategy['max_total_orders'] = max(strategy['min_total_orders'], min(int(strategy.get('max_total_orders', 9999)), 10000))
    strategy['min_total_revenue'] = max(0.0, float(strategy.get('min_total_revenue', 0.0)))
    strategy['max_active_sales_now'] = max(0, min(int(strategy.get('max_active_sales_now', 999)), 999))
    return strategy


def _build_audience_recommendations(campaign, limit=250):
    campaign.recommendations.all().delete()
    now = timezone.now()
    base_qs = Sale.objects.filter(status=True, created_at__gte=now - timedelta(days=365))
    if campaign.created_by and not campaign.created_by.is_superuser:
        base_qs = base_qs.filter(user_seller=campaign.created_by)

    catalog_rows = list(
        base_qs.values('account_id', 'account__account_name__description')
        .annotate(total_sales=Count('id'))
        .order_by('-total_sales')[:50]
    )
    target_service_ids = set()
    search_text = f"{campaign.name or ''} {campaign.objective or ''} {campaign.idea_input or ''} {campaign.message_text or ''}".lower()
    for item in catalog_rows:
        desc = str(item.get('account__account_name__description') or '').strip().lower()
        if desc and desc in search_text:
            target_service_ids.add(item['account_id'])
    if not target_service_ids and catalog_rows:
        target_service_ids.add(catalog_rows[0]['account_id'])
    strategy = _infer_audience_strategy(campaign)
    for keyword in strategy.get('service_keywords', []):
        for item in catalog_rows:
            desc = str(item.get('account__account_name__description') or '').strip().lower()
            if keyword and keyword in desc:
                target_service_ids.add(item['account_id'])
    countries_include = set(strategy.get('countries_include', []))
    countries_exclude = set(strategy.get('countries_exclude', []))

    rows = (
        base_qs.values(
            'customer_id',
            'customer__username',
            'customer__email',
            'customer__userdetail__country',
            'customer__userdetail__lada',
            'customer__userdetail__phone_number',
        )
        .annotate(
            total_orders=Count('id'),
            total_revenue=Sum('payment_amount'),
            last_purchase=Max('created_at'),
        )
        .order_by('-total_revenue')[:800]
    )

    objective = (campaign.objective or '').lower()
    for row in rows:
        total_revenue = float(row.get('total_revenue') or 0)
        total_orders = int(row.get('total_orders') or 0)
        last_purchase = row.get('last_purchase')
        days_inactive = (now - last_purchase).days if last_purchase else 999
        recency_score = max(0, 180 - days_inactive)
        score = (total_revenue * 0.03) + (total_orders * 3) + recency_score
        if 'reactiv' in objective:
            score = (total_revenue * 0.02) + (total_orders * 2) + (days_inactive * 1.1)
        if 'alto valor' in objective or 'premium' in objective:
            score = (total_revenue * 0.06) + (total_orders * 2) + recency_score

        recent_same_service = False
        service_history = 0
        target_last_purchase = None
        target_days_inactive = 999
        target_active_now = False
        active_sales_now = Sale.objects.filter(
            customer_id=row['customer_id'],
            status=True,
            expiration_date__gte=now,
        ).count()
        if target_service_ids:
            recent_same_service = Sale.objects.filter(
                customer_id=row['customer_id'],
                account_id__in=target_service_ids,
                status=True,
                created_at__gte=now - timedelta(days=2),
            ).exists()
            service_history = Sale.objects.filter(
                customer_id=row['customer_id'],
                account_id__in=target_service_ids,
                status=True,
                created_at__lt=now - timedelta(days=2),
            ).count()
            target_last_purchase = Sale.objects.filter(
                customer_id=row['customer_id'],
                account_id__in=target_service_ids,
            ).aggregate(last=Max('created_at')).get('last')
            if target_last_purchase:
                target_days_inactive = (now - target_last_purchase).days
            target_active_now = Sale.objects.filter(
                customer_id=row['customer_id'],
                account_id__in=target_service_ids,
                status=True,
                expiration_date__gte=now,
            ).exists()
            score += min(service_history * 4, 32)

        eligible = True
        country_value = _mysql_safe_text(row.get('customer__userdetail__country') or '').strip().lower()
        if countries_include and country_value not in countries_include:
            eligible = False
        if country_value and country_value in countries_exclude:
            eligible = False
        if days_inactive < strategy.get('min_days_inactive', 0) or days_inactive > strategy.get('max_days_inactive', 3650):
            eligible = False
        if total_orders < strategy.get('min_total_orders', 0) or total_orders > strategy.get('max_total_orders', 9999):
            eligible = False
        if total_revenue < strategy.get('min_total_revenue', 0):
            eligible = False
        if strategy.get('require_no_active_sales') and active_sales_now > 0:
            eligible = False
        if active_sales_now > strategy.get('max_active_sales_now', 999):
            eligible = False
        if strategy.get('require_service_history') and service_history <= 0 and not target_last_purchase:
            eligible = False
        if strategy.get('require_target_service_inactive') and target_active_now:
            eligible = False
        if recent_same_service and strategy.get('exclude_recent_same_service_days', 0) > 0:
            eligible = False

        has_phone = bool(row.get('customer__userdetail__lada')) and bool(row.get('customer__userdetail__phone_number'))
        if campaign.channel in ('whatsapp', 'sms') and not has_phone:
            eligible = False

        segment_type = strategy.get('segment_type', 'general')
        if segment_type == 'reactivation':
            score = (total_revenue * 0.02) + (service_history * 4) + min(target_days_inactive * 0.9, 160)
        elif segment_type == 'upsell':
            score = (total_revenue * 0.05) + (total_orders * 4) + max(0, 90 - days_inactive)
        elif segment_type == 'cross_sell':
            score = (total_revenue * 0.04) + (total_orders * 3) + max(0, 120 - days_inactive)
        elif segment_type == 'retention':
            score = (total_revenue * 0.03) + (total_orders * 3.5) + max(0, 45 - days_inactive) * 2
        elif segment_type == 'premium':
            score = (total_revenue * 0.08) + (total_orders * 4) + max(0, 120 - days_inactive)
        elif segment_type == 'acquisition':
            score = (total_orders * 2) + max(0, days_inactive - 30)
        elif segment_type == 'churn_risk':
            score = (total_revenue * 0.03) + (total_orders * 2) + min(max(days_inactive - 20, 0), 140)
        if not eligible:
            score = 0

        reason = (
            f"Ordenes={total_orders}, Ingreso={round(total_revenue, 2)}, "
            f"Dias sin compra={days_inactive}, Historial servicio={service_history}, "
            f"Dias sin compra objetivo={target_days_inactive}, Activas ahora={active_sales_now}, "
            f"Segmento={strategy.get('segment_type', 'general')}, Elegible={eligible}"
        )
        MarketingCampaignRecommendation.objects.create(
            campaign=campaign,
            customer_id=row['customer_id'],
            country=row.get('customer__userdetail__country') or '',
            lada=str(row.get('customer__userdetail__lada') or ''),
            phone_number=str(row.get('customer__userdetail__phone_number') or ''),
            total_orders=total_orders,
            total_revenue=round(total_revenue, 2),
            last_purchase=last_purchase,
            score=round(score, 2),
            reason=reason,
            selected=eligible and score > 0,
        )

    keep_ids = list(
        campaign.recommendations.filter(selected=True).order_by('-score').values_list('id', flat=True)[:limit]
    )
    campaign.recommendations.exclude(id__in=keep_ids).delete()
    campaign.audience_filters = campaign.audience_filters or {}
    campaign.audience_filters['audience_strategy'] = strategy
    campaign.save(update_fields=['audience_filters', 'updated_at'])


def _generate_clarification_questions(campaign, from_scratch=False):
    provider = get_active_provider()
    text_model = get_model_for_task('text', provider=provider)
    client = AIClient.from_settings(timeout=45)
    stats = _marketing_stats_snapshot(campaign.created_by or User.objects.filter(is_superuser=True).first() or User.objects.first())
    db_context = _marketing_db_context(campaign.created_by)
    objective = (campaign.objective or '').strip() or 'Maximizar conversión con segmentación específica'
    idea_input = (campaign.idea_input or '').strip()
    if from_scratch:
        idea_input = "Generación desde cero basada exclusivamente en estadísticas."

    prompt = (
        "Eres estratega de growth marketing.\n"
        "Debes decidir si necesitas preguntar algo antes de generar una campaña excelente.\n"
        "Si hay incertidumbre relevante (margen, límites de descuento, tono de marca, inventario, restricción legal), haz hasta 3 preguntas concretas.\n"
        "Si no hace falta preguntar, devuelve lista vacía.\n"
        "Devuelve SOLO JSON: {\"questions\":[\"...\",\"...\"]}\n\n"
        f"Canal: {campaign.channel}\n"
        f"Objetivo: {objective}\n"
        f"Idea inicial: {idea_input}\n"
        f"Estadísticas: {json.dumps(stats, ensure_ascii=False, default=str)}\n"
        f"Contexto SQL: {json.dumps(db_context, ensure_ascii=False, default=str)}"
    )
    result = client.generate(
        model=text_model,
        prompt=prompt,
        system_prompt="Responde solo JSON válido.",
        temperature=0.2,
        max_output_tokens=400,
    )
    payload = _marketing_parse_json(result.text)
    questions = payload.get('questions') if isinstance(payload.get('questions'), list) else []
    cleaned = []
    for q in questions[:3]:
        value = _mysql_safe_text(q).strip()
        if value:
            cleaned.append(value)
    return cleaned


def _generate_campaign_ai_content(campaign, from_scratch=False):
    stats = _marketing_stats_snapshot(campaign.created_by or User.objects.filter(is_superuser=True).first() or User.objects.first())
    db_context = _marketing_db_context(campaign.created_by)
    campaign.stats_snapshot = stats
    meta = campaign.audience_filters or {}
    clarification_answers = meta.get('clarification_answers') if isinstance(meta.get('clarification_answers'), list) else []

    provider = get_active_provider()
    text_model = get_model_for_task('text', provider=provider)
    client = AIClient.from_settings(timeout=70)
    objective = (campaign.objective or '').strip() or 'Maximizar conversión con segmentación específica'
    idea_input = (campaign.idea_input or '').strip()
    if from_scratch:
        idea_input = (
            "Generar desde cero con base exclusiva en estadísticas. "
            "Diseñar campaña hiper-específica, accionable y medible."
        )
    prompt = (
        "Eres estratega senior de growth marketing y marketing digital orientado a conversion.\n"
        "Diseña una campaña solo para WhatsApp (imagen+texto) o SMS (solo texto).\n"
        "Debe ser hiper-específica, concreta, con microsegmento y accionable, nunca general.\n"
        "Debe basarse 100% en estadísticas y aplicar principios de growth: segmentación, hipótesis, oferta, urgencia, CTA y medición.\n"
        "Evita mensajes amplios, vagos o de branding genérico.\n"
        "NO menciones estadísticas internas, porcentajes, ni frases como 'vimos que' o 'últimos 90 días' en el copy final.\n"
        "El mensaje final debe sonar comercial, directo, emocional y con urgencia real.\n"
        "WhatsApp: usar formato visual atractivo con emojis y markdown breve (negritas/listas cortas), estilo anuncio listo para enviar.\n"
        "SMS: texto corto, claro, sin markdown complejo, con CTA único.\n"
        "Devuelve SOLO JSON con:\n"
        "{"
        "\"campaign_name\":\"...\","
        "\"whatsapp_text\":\"...\","
        "\"sms_text\":\"...\","
        "\"image_prompt\":\"...\","
        "\"tags\":[\"...\"],"
        "\"targeting_notes\":\"...\","
        "\"cta\":\"...\","
        "\"growth_hypothesis\":\"...\","
        "\"kpi_focus\":\"...\""
        "}\n\n"
        f"Canal: {campaign.channel}\n"
        f"Objetivo: {objective}\n"
        f"Idea inicial: {idea_input}\n"
        f"Respuestas de aclaración del usuario: {json.dumps(clarification_answers, ensure_ascii=False, default=str)}\n"
        f"Estadísticas: {json.dumps(stats, ensure_ascii=False)}\n"
        f"Contexto SQL solo lectura: {json.dumps(db_context, ensure_ascii=False, default=str)}"
    )

    result = client.generate(
        model=text_model,
        prompt=prompt,
        system_prompt="Responde solo JSON válido sin markdown.",
        max_output_tokens=1100,
        temperature=0.4,
    )
    payload = _marketing_parse_json(result.text)
    campaign.ai_prompt_used = _mysql_safe_text(prompt)
    campaign.name = _mysql_safe_text(payload.get('campaign_name') or campaign.name)
    campaign.message_text = _mysql_safe_text(
        payload.get('whatsapp_text') or campaign.message_text or campaign.idea_input
    )
    campaign.sms_text = _mysql_safe_text(payload.get('sms_text') or campaign.sms_text or campaign.message_text)
    campaign.image_prompt = _mysql_safe_text(
        payload.get('image_prompt') or campaign.image_prompt or f"Promocion marketing para {campaign.objective}"
    )
    if isinstance(payload.get('tags'), list):
        campaign.tags = [_mysql_safe_text(t) for t in payload.get('tags')[:20]]
    else:
        campaign.tags = ['marketing', campaign.channel, 'ia']
    campaign.audience_filters = {
        'targeting_notes': _mysql_safe_text(payload.get('targeting_notes', '')),
        'cta': _mysql_safe_text(payload.get('cta', '')),
        'growth_hypothesis': _mysql_safe_text(payload.get('growth_hypothesis', '')),
        'kpi_focus': _mysql_safe_text(payload.get('kpi_focus', '')),
        'generation_mode': 'from_stats_only' if from_scratch else 'from_idea',
        'db_context_errors': db_context.get('errors', []),
    }

    image_generation_response = {'status': 'not_requested', 'provider': '', 'model': '', 'message': ''}
    if campaign.channel == 'whatsapp':
        image_generation_response = _generate_campaign_image(campaign)

    campaign.status = 'ready'
    campaign.audience_filters = campaign.audience_filters or {}
    campaign.audience_filters['image_generation_response'] = image_generation_response
    campaign.save()
    _build_audience_recommendations(campaign, limit=300)


def _generate_campaign_image(campaign):
    image_generation_response = {'status': 'not_requested', 'provider': '', 'model': '', 'message': ''}
    if campaign.channel == 'whatsapp':
        requested_model = os.getenv('AI_MARKETING_GEMINI_IMAGE_MODEL', 'nano-banana2').strip() or 'nano-banana2'
        model_alias = {
            'nano-banana2': 'gemini-3.1-flash-image-preview',
            'nano banana 2': 'gemini-3.1-flash-image-preview',
            'nano-banana': 'gemini-2.5-flash-image',
            'nano-banana-pro': 'gemini-3-pro-image-preview',
        }
        requested_model = model_alias.get(requested_model.lower(), requested_model)
        fallback_model = get_model_for_task('image', provider='gemini') or 'gemini-2.5-flash-image'
        candidate_models = []
        for m in [
            requested_model,
            'gemini-3.1-flash-image-preview',
            fallback_model,
            'gemini-3-pro-image-preview',
            'gemini-2.5-flash-image',
            'gemini-2.0-flash-preview-image-generation',
        ]:
            m = str(m or '').strip()
            if m and m not in candidate_models:
                candidate_models.append(m)
        try:
            gemini_client = AIClient.from_provider_name('gemini', timeout=90)
            errors = []
            image_result = None
            used_model = ''
            for model_name in candidate_models:
                try:
                    image_result = gemini_client.generate_image(prompt=campaign.image_prompt, model=model_name)
                    if image_result.images_base64:
                        used_model = model_name
                        break
                    errors.append(f'{model_name}: sin imagen en respuesta')
                except Exception as exc:
                    errors.append(f'{model_name}: {_error_to_text(exc)}')

            if image_result and image_result.images_base64:
                img = base64.b64decode(image_result.images_base64[0])
                img = _force_square_image_bytes(img)
                filename = f"campaign_{campaign.id}_{timezone.now().strftime('%Y%m%d%H%M%S')}.png"
                campaign.creative_image.save(filename, ContentFile(img), save=False)
                image_generation_response = {
                    'status': 'ok',
                    'provider': 'gemini',
                    'model': used_model,
                    'message': _mysql_safe_text(
                        'Imagen generada correctamente. Intentos: ' + ', '.join(candidate_models)
                    ),
                }
            else:
                image_generation_response = {
                    'status': 'failed',
                    'provider': 'gemini',
                    'model': requested_model,
                    'message': _mysql_safe_text('No se pudo generar imagen. Detalle: ' + ' | '.join(errors)),
                }
        except Exception as exc:
            image_generation_response = {
                'status': 'failed',
                'provider': 'gemini',
                'model': requested_model,
                'message': _error_to_text(exc),
            }
    campaign.audience_filters = campaign.audience_filters or {}
    campaign.audience_filters['image_generation_response'] = image_generation_response
    campaign.save(update_fields=['creative_image', 'audience_filters', 'updated_at'])
    return image_generation_response


def _run_marketing_generation_job(campaign_id, from_scratch, allow_questions=True):
    try:
        campaign = MarketingCampaign.objects.get(pk=campaign_id)
        if allow_questions:
            questions = _generate_clarification_questions(campaign, from_scratch=from_scratch)
            if questions:
                campaign.audience_filters = campaign.audience_filters or {}
                campaign.audience_filters['generation_status'] = 'needs_input'
                campaign.audience_filters['clarification_questions'] = questions
                campaign.audience_filters['clarification_answers'] = []
                campaign.save(update_fields=['audience_filters', 'updated_at'])
                return
        _generate_campaign_ai_content(campaign, from_scratch=from_scratch)
        campaign.audience_filters = campaign.audience_filters or {}
        campaign.audience_filters['generation_status'] = 'done'
        campaign.save(update_fields=['audience_filters', 'updated_at'])
    except Exception as exc:
        try:
            campaign = MarketingCampaign.objects.get(pk=campaign_id)
            campaign.audience_filters = campaign.audience_filters or {}
            campaign.audience_filters['generation_status'] = 'error'
            campaign.audience_filters['generation_error'] = str(exc)
            campaign.save(update_fields=['audience_filters', 'updated_at'])
        except Exception:
            pass


@permission_required('is_superuser', 'adm:no-permission')
def marketing_campaigns(request):
    qs = MarketingCampaign.objects.all().order_by('-created_at')
    status = request.GET.get('status', '').strip()
    channel = request.GET.get('channel', '').strip()
    q = request.GET.get('q', '').strip()
    if status:
        qs = qs.filter(status=status)
    if channel:
        qs = qs.filter(channel=channel)
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(objective__icontains=q) | Q(idea_input__icontains=q))
    campaigns = Paginator(qs, 30).get_page(request.GET.get('page', 1))
    return render(
        request,
        'adm/marketing/campaigns.html',
        {'campaigns': campaigns, 'status': status, 'channel': channel, 'q': q},
    )


@permission_required('is_superuser', 'adm:no-permission')
def marketing_campaign_create(request):
    if request.method == 'POST':
        form = MarketingCampaignForm(request.POST)
        if form.is_valid():
            campaign = form.save(commit=False)
            campaign.created_by = request.user
            campaign.status = 'draft'
            campaign.save()
            action = request.POST.get('action', 'generate')
            if action in ('generate', 'generate_stats') and request.headers.get('x-requested-with') == 'XMLHttpRequest':
                campaign.audience_filters = campaign.audience_filters or {}
                campaign.audience_filters['generation_status'] = 'processing'
                campaign.audience_filters['generation_error'] = ''
                campaign.save(update_fields=['audience_filters', 'updated_at'])
                from_scratch = action == 'generate_stats'
                Thread(
                    target=_run_marketing_generation_job,
                    args=(campaign.id, from_scratch, True),
                    daemon=True,
                ).start()
                return JsonResponse(
                    {
                        'success': True,
                        'queued': True,
                        'campaign_id': campaign.id,
                        'detail_url': reverse('adm:marketing_campaign_detail', kwargs={'pk': campaign.id}),
                        'status_url': reverse('adm:marketing_campaign_generation_status', kwargs={'pk': campaign.id}),
                    }
                )

            if action == 'generate':
                try:
                    _generate_campaign_ai_content(campaign)
                    messages.success(request, 'Campaña generada con IA correctamente.')
                except Exception as exc:
                    messages.warning(
                        request,
                        f'La campaña se guardó en borrador, pero falló la generación IA: {exc}'
                    )
            elif action == 'generate_stats':
                try:
                    _generate_campaign_ai_content(campaign, from_scratch=True)
                    messages.success(
                        request,
                        'Campaña creada desde cero con IA, basada solo en estadísticas.'
                    )
                except Exception as exc:
                    messages.warning(
                        request,
                        f'La campaña se guardó en borrador, pero falló la generación desde estadísticas: {exc}'
                    )
            else:
                messages.success(request, 'Campaña guardada en borrador.')
            return redirect('adm:marketing_campaign_detail', campaign.id)
    else:
        form = MarketingCampaignForm()
    return render(
        request,
        'adm/marketing/campaign_create.html',
        {'form': form, 'preview_stats': _marketing_stats_snapshot(request.user)},
    )


@permission_required('is_superuser', 'adm:no-permission')
def marketing_campaign_detail(request, pk):
    campaign = MarketingCampaign.objects.get(pk=pk)
    meta = campaign.audience_filters or {}
    return render(
        request,
        'adm/marketing/campaign_detail.html',
        {
            'campaign': campaign,
            'recommendations': campaign.recommendations.filter(selected=True).order_by('-score')[:350],
            'deliveries': campaign.deliveries.order_by('-created_at')[:350],
            'stats': campaign.stats_snapshot or {},
            'audience_strategy': meta.get('audience_strategy', {}),
        },
    )


@permission_required('is_superuser', 'adm:no-permission')
def marketing_campaign_generation_status(request, pk):
    campaign = MarketingCampaign.objects.get(pk=pk)
    meta = campaign.audience_filters or {}
    status_value = meta.get('generation_status', '')
    error = meta.get('generation_error', '')
    done = status_value in ('done', 'error') or campaign.status == 'ready'
    return JsonResponse(
        {
            'success': True,
            'campaign_id': campaign.id,
            'generation_status': status_value or ('done' if campaign.status == 'ready' else 'processing'),
            'error': error,
            'done': done,
            'questions': meta.get('clarification_questions', []),
            'detail_url': reverse('adm:marketing_campaign_detail', kwargs={'pk': campaign.id}),
        }
    )


@permission_required('is_superuser', 'adm:no-permission')
def marketing_campaign_answer_clarifications(request, pk):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)
    campaign = MarketingCampaign.objects.get(pk=pk)
    meta = campaign.audience_filters or {}
    questions = meta.get('clarification_questions') if isinstance(meta.get('clarification_questions'), list) else []
    answers = []
    for idx, _ in enumerate(questions):
        val = _mysql_safe_text(request.POST.get(f'answer_{idx}', '')).strip()
        answers.append(val)
    if not any(answers):
        return JsonResponse({'success': False, 'error': 'Responde al menos una pregunta'}, status=400)
    meta['clarification_answers'] = answers
    meta['generation_status'] = 'processing'
    campaign.audience_filters = meta
    campaign.save(update_fields=['audience_filters', 'updated_at'])
    Thread(
        target=_run_marketing_generation_job,
        args=(campaign.id, meta.get('generation_mode') == 'from_stats_only', False),
        daemon=True,
    ).start()
    return JsonResponse(
        {
            'success': True,
            'campaign_id': campaign.id,
            'status_url': reverse('adm:marketing_campaign_generation_status', kwargs={'pk': campaign.id}),
            'detail_url': reverse('adm:marketing_campaign_detail', kwargs={'pk': campaign.id}),
        }
    )


@permission_required('is_superuser', 'adm:no-permission')
def marketing_campaign_feedback(request, pk):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)
    campaign = MarketingCampaign.objects.get(pk=pk)
    question = (request.POST.get('question') or '').strip()
    extra_sql = (request.POST.get('extra_sql') or '').strip()
    if not question:
        return JsonResponse({'success': False, 'error': 'Pregunta requerida'}, status=400)

    db_context = _marketing_db_context(campaign.created_by)
    sql_extra_result = None
    if extra_sql:
        cfg = get_db_mcp_config()
        mcp = ReadOnlyDatabaseMCP(
            allowed_tables=cfg["allowed_tables"] or None,
            max_rows=min(int(cfg["max_rows"]), 300),
            include_schema=False,
        )
        try:
            qr = mcp.query(extra_sql, params=[], limit=200)
            sql_extra_result = {
                'sql': _mysql_safe_text(qr.sql),
                'row_count': qr.row_count,
                'rows': qr.rows,
            }
        except Exception as exc:
            return JsonResponse({'success': False, 'error': f'SQL inválido o no permitido: {exc}'}, status=400)

    provider = get_active_provider()
    text_model = get_model_for_task('text', provider=provider)
    client = AIClient.from_settings(timeout=70)
    prompt = (
        "Eres consultor senior de growth marketing y pricing.\n"
        "Analiza la pregunta de retroalimentación de campaña usando SOLO evidencia del contexto.\n"
        "Puedes recomendar ajustes de precio, cupón o mensaje, sin romper rentabilidad.\n"
        "Responde en markdown claro con: conclusión, razonamiento breve, recomendación accionable.\n"
        "Si faltan datos para validar margen/utilidad, dilo explícitamente y sugiere siguiente consulta SQL de solo lectura.\n\n"
        f"Campaña actual: {json.dumps({'id': campaign.id, 'name': campaign.name, 'channel': campaign.channel, 'objective': campaign.objective, 'message_text': campaign.message_text, 'sms_text': campaign.sms_text, 'tags': campaign.tags}, ensure_ascii=False, default=str)}\n"
        f"Contexto SQL marketing: {json.dumps(db_context, ensure_ascii=False, default=str)}\n"
        f"SQL adicional del usuario: {json.dumps(sql_extra_result, ensure_ascii=False, default=str)}\n"
        f"Pregunta del usuario: {question}"
    )
    try:
        result = client.generate(
            model=text_model,
            prompt=prompt,
            system_prompt="Responde en español. No inventes datos no presentes.",
            max_output_tokens=1200,
            temperature=0.35,
        )
        answer = _mysql_safe_text(result.text or '')
    except Exception as exc:
        return JsonResponse({'success': False, 'error': f'No se pudo generar respuesta IA: {exc}'}, status=500)

    meta = campaign.audience_filters or {}
    history = meta.get('feedback_history') or []
    history.append(
        {
            'at': timezone.now().isoformat(),
            'question': _mysql_safe_text(question),
            'extra_sql': _mysql_safe_text(extra_sql),
            'answer': answer,
        }
    )
    meta['feedback_history'] = history[-40:]
    campaign.audience_filters = meta
    campaign.save(update_fields=['audience_filters', 'updated_at'])
    return JsonResponse({'success': True, 'answer': answer, 'history_count': len(meta['feedback_history'])})


@permission_required('is_superuser', 'adm:no-permission')
def marketing_campaign_regenerate_image(request, pk):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)
    campaign = MarketingCampaign.objects.get(pk=pk)
    if campaign.channel != 'whatsapp':
        return JsonResponse({'success': False, 'error': 'Solo aplica para campañas de WhatsApp'}, status=400)
    new_prompt = _mysql_safe_text((request.POST.get('image_prompt') or '').strip())
    if new_prompt:
        campaign.image_prompt = new_prompt
        campaign.save(update_fields=['image_prompt', 'updated_at'])
    try:
        image_meta = _generate_campaign_image(campaign)
    except Exception as exc:
        return JsonResponse({'success': False, 'error': _error_to_text(exc)}, status=500)
    return JsonResponse(
        {
            'success': image_meta.get('status') == 'ok',
            'image_response': image_meta,
            'image_url': campaign.creative_image.url if campaign.creative_image else '',
            'message': image_meta.get('message', ''),
        }
    )


@permission_required('is_superuser', 'adm:no-permission')
def marketing_campaign_regenerate(request, pk):
    campaign = MarketingCampaign.objects.get(pk=pk)
    try:
        _generate_campaign_ai_content(campaign)
        messages.success(request, 'Campaña regenerada con IA correctamente.')
    except Exception as exc:
        messages.warning(request, f'No se pudo regenerar la campaña con IA: {exc}')
    return redirect('adm:marketing_campaign_detail', campaign.id)


@permission_required('is_superuser', 'adm:no-permission')
def marketing_campaign_send(request, pk):
    campaign = MarketingCampaign.objects.get(pk=pk)
    selected = campaign.recommendations.filter(selected=True).order_by('-score')[:350]
    actual_send_enabled = os.getenv('AI_MARKETING_ACTUAL_SEND', 'false').lower() in ('1', 'true', 'yes', 'on')
    send_now = request.POST.get('send_now', 'false') == 'true'
    sent_count = 0
    failed_count = 0

    for rec in selected:
        if campaign.channel == 'whatsapp':
            destination = f"+{rec.lada}{rec.phone_number}" if rec.lada and rec.phone_number else rec.customer.email
            status_value = 'queued'
            response_message = 'Registrado en histórico'
            if send_now and actual_send_enabled and rec.lada and rec.phone_number and campaign.message_text:
                try:
                    Notification.send_whatsapp_notification(campaign.message_text, rec.lada, rec.phone_number)
                    status_value = 'sent'
                    response_message = 'WhatsApp enviado'
                    sent_count += 1
                except Exception as exc:
                    status_value = 'failed'
                    response_message = str(exc)
                    failed_count += 1
            else:
                sent_count += 1

            MarketingCampaignDelivery.objects.create(
                campaign=campaign,
                recommendation=rec,
                channel='whatsapp',
                destination=destination,
                payload_text=campaign.message_text or '',
                payload_image_url=campaign.creative_image.url if campaign.creative_image else '',
                status=status_value,
                provider_response=response_message,
                sent_at=timezone.now() if status_value in ('sent', 'queued') else None,
            )
        else:
            destination = f"+{rec.lada}{rec.phone_number}" if rec.lada and rec.phone_number else rec.customer.email
            sent_count += 1
            MarketingCampaignDelivery.objects.create(
                campaign=campaign,
                recommendation=rec,
                channel='sms',
                destination=destination,
                payload_text=(campaign.sms_text or campaign.message_text or '')[:1600],
                status='queued',
                provider_response='SMS registrado en histórico (sin proveedor configurado).',
                sent_at=timezone.now(),
            )

    campaign.status = 'sent'
    campaign.sent_at = timezone.now()
    campaign.save(update_fields=['status', 'sent_at', 'updated_at'])

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'sent_count': sent_count, 'failed_count': failed_count})
    return redirect('adm:marketing_campaign_detail', campaign.id)


@permission_required('is_superuser', 'adm:no-permission')
def marketing_campaign_recommendations_csv(request, pk):
    campaign = MarketingCampaign.objects.get(pk=pk)
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="marketing_campaign_{campaign.id}_audience.csv"'
    writer = csv.writer(response)
    writer.writerow([
        'customer_id', 'username', 'email', 'country', 'lada', 'phone_number',
        'total_orders', 'total_revenue', 'last_purchase', 'score', 'reason',
    ])
    for r in campaign.recommendations.order_by('-score'):
        writer.writerow([
            r.customer_id,
            r.customer.username,
            r.customer.email,
            r.country or '',
            r.lada or '',
            r.phone_number or '',
            r.total_orders,
            r.total_revenue,
            timezone.localtime(r.last_purchase).strftime('%Y-%m-%d %H:%M:%S') if r.last_purchase else '',
            r.score,
            r.reason or '',
        ])
    return response
