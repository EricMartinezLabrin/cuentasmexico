# Django
import json
from django.shortcuts import render
from django.http import HttpResponse, HttpRequest
from django.views.generic import DetailView, CreateView, UpdateView, TemplateView, ListView, DeleteView
from django.urls import reverse, reverse_lazy
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.models import User
from django.shortcuts import redirect
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.http import JsonResponse
from django.db.models import Sum, Prefetch
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.db.models import DateTimeField, ExpressionWrapper, F
from calendar import monthrange
# Python
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import requests
from adm.functions.send_whatsapp_notification import Notification
from api.functions.notifications import send_push_notification
import pyperclip as clipboard
from django.db.models import DurationField
# import pandas as pd
# Local
from .models import Business, PaymentMethod, Sale, UserDetail, Service, Account, Bank, Status, Supplier, Credits
from cupon.models import Cupon
from .functions.alerts import Alerts
from .functions.forms import AccountsForm, BankForm, PaymentMethodForm, ServicesForm, SettingsForm, UserDetailForm, UserForm, FilterAccountForm, StatusForm, SupplierForm, CustomerUpdateForm, UserMainForm
from .functions.permissions import UserAccessMixin
from .functions.country import Country
from .functions.active_inactive import Active_Inactive
from .functions.dashboard import Dashboard
from adm.functions.duplicated import NoDuplicate
from adm.functions.sales import Sales
# from adm.functions.import_data import ImportData
from adm.db.constants import URL
import os

def is_ajax(request):
    return request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest'

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
    return render(request, template_name, {
        'sales_day': sales_day,
        'sales_month': sales_month,
        'acc_name': sales_acc[0],
        'acc_total': sales_acc[1],
        'time': timezone.now(),
        'last_year_sales_new_user': Dashboard.last_year_sales_new_user(),
        'sales_per_day_new_user':Dashboard.sales_per_day_new_user(date)
    })

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
    return render(request, template_name, {
        'object': business_detail
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

class UserView(UserAccessMixin, ListView):
    """
    Here you can view all users of page
    """
    permission_required = 'is_staff'
    model = User
    template_name = 'adm/user.html'
    permission_required = 'is_superuser'
    paginate_by = 30

class ServiceView(UserAccessMixin, ListView):
    """
    Here you can see all Available Services
    """
    permission_required = 'is_staff'
    model = Service
    template_name = 'adm/services.html'

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
    if request.method == 'POST' or any([account_name, email, status]):
        # Aplicar filtros de manera eficiente
        if account_name:
            base_queryset = base_queryset.filter(account_name=account_name)
        if email:
            base_queryset = base_queryset.filter(email__icontains=email)
        if status:
            base_queryset = base_queryset.filter(status=status == 'True')
        
        # Ordenar de manera eficiente
        accounts = base_queryset.order_by('-created_at', 'profile')
        
        # Preparar datos del formulario
        form_data = {
            'account_name': account_name,
            'email': email,
            'status': status
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
        
        filter_query = '&'.join(filter_params)
        
        # Crear contexto sin objetos que no se pueden serializar
        context = {
            "venues": venues,
            "form": FilterAccountForm(),
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
        comments = request.POST.get('comments')
        if request.POST.get('renovable') == 'on':
            renovable = True
        else:
            renovable = False
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
                profile=i
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

@permission_required('is_staff', 'adm:no-permission')
def ActiveInactiveAccount(request, status, pk):
    account = Account.objects.get(pk=pk)
    account.status = Active_Inactive.active_inactive(status)
    account.save()
    return redirect(reverse('adm:accounts'))

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
    if request.method == 'POST':
        if Sales.new_sale(request) == True:
            customer = User.objects.get(pk=pk)
            return Sales.render_view(request, customer)
    return render(request, template_name, {
        'customer': User.objects.get(pk=pk),
        'services': Sales.availables()[1],
        'bank': bank,
        'payment': payment,
        'availables': Sales.availables()[0],
        'created_at': timezone.now()
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
    print('empezo')
    if is_ajax(request):
        print('entro al ajax')
        res = None
        services = request.POST.getlist('data[]', '')
        print(services)
        print(res)
        data = []
        if services:
            for s in services:
                service = Service.objects.get(pk=int(json.loads(s)['service']))
                acc = Account.objects.filter(
                    account_name=service, customer=None, status=True).order_by('-expiration_date')
                if not json.loads(s)['duration'] == 'None':
                    # Establece una fecha de expiración de dos meses
                    better_acc_expiration_date = timezone.now(
                    ) + relativedelta(months=int(json.loads(s)['duration']))
                    # Busca la cuenta más adecuada
                    better_acc = Sales.search_better_acc(
                        service.id, better_acc_expiration_date)
                    # Agrega los detalles de la cuenta más adecuada a la lista
                    print(better_acc)
                    if better_acc and better_acc[0] == True:
                        data.append({
                            'id': better_acc[1].id,
                            'logo': str(better_acc[1].account_name.logo),
                            'acc_name': better_acc[1].account_name.description,
                            'email': better_acc[1].email,
                            'password': better_acc[1].password,
                            'expiration_acc': better_acc[1].expiration_date,
                            'profile': better_acc[1].profile
                        })
                        for other_acc in acc:
                            if other_acc.id != better_acc[1].id:
                                item = {
                                    'id': other_acc.id,
                                    'logo': str(other_acc.account_name.logo),
                                    'acc_name': other_acc.account_name.description,
                                    'email': other_acc.email,
                                    'password': other_acc.password,
                                    'expiration_acc': other_acc.expiration_date,
                                    'profile': other_acc.profile
                                }
                                data.append(item)
                    else:
                        for other_acc in acc:
                            item = {
                                'id': other_acc.id,
                                'logo': str(other_acc.account_name.logo),
                                'acc_name': other_acc.account_name.description,
                                'email': other_acc.email,
                                'password': other_acc.password,
                                'expiration_acc': other_acc.expiration_date,
                                'profile': other_acc.profile
                            }
                            data.append(item)
                # Si no tiene duración definida, establece una fecha de expiración de dos meses
                else:
                    expiration_date = timezone.now() + relativedelta(months=2)
                    # Agrega los detalles de las cuentas disponibles a la lista
                    for pos in acc:
                        item = {
                            'id': pos.id,
                            'logo': str(pos.account_name.image),
                            'acc_name': pos.account_name.name,
                            'email': pos.email,
                            'password': pos.password,
                            'expiration_acc': pos.expiration_date,
                            'profile': pos.profile
                        }
                        data.append(item)
                    # Establece el resultado como la lista de detalles de cuentas
                    res = data
                if len(acc) > 0 and len(services) > 0:
                    for pos in acc:
                        item = {
                            'id': pos.id,
                            'logo': str(pos.account_name.logo),
                            'acc_name': pos.account_name.description,
                            'email': pos.email,
                            'password': pos.password,
                            'expiration_acc': pos.expiration_date,
                            'profile': pos.profile
                        }
                        data.append(item)
                    res = data
                else:
                    res = "No hay cuentas disponibles"
            return JsonResponse({'data': res})
        else:
            res = "No hay cuentas seleccionadas"
        return JsonResponse({'data': res})
    elif request.method == 'POST':
        data_array = []
        data = json.loads(request.body)
        service_id = int(data['data']['service'])
        code_name = data['data']['code']
        code = Cupon.objects.get(name=code_name)
        service = Service.objects.get(pk=service_id)
        duration = code.long
        accounts = Account.objects.filter(
            account_name=service, customer=None, status=True).order_by('-expiration_date')
        if duration == 0.25:
            better_acc_expiration_date = timezone.now() + timedelta(days=7)
        else:
            better_acc_expiration_date = timezone.now() + relativedelta(months=duration)
        better_acc = Sales.search_better_acc(
            service.id, better_acc_expiration_date)
        if better_acc[0] == False:
            return JsonResponse({'data': 'No hay cuentas disponibles'})
        else:
            data_array.append({
                'id': better_acc[1].id,
                'logo': str(better_acc[1].account_name.image),
                'acc_name': better_acc[1].account_name.name,
                'email': better_acc[1].email,
                'password': better_acc[1].password,
                'expiration_acc': better_acc[1].expiration_date,
                'profile': better_acc[1].profile
            })
            for other_acc in accounts:
                if other_acc.id != better_acc[1].id:
                    item = {
                        'id': other_acc.id,
                        'logo': str(other_acc.account_name.image),
                        'acc_name': other_acc.account_name.name,
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
                            'logo': str(pos.account_name.logo),
                            'email': pos.email,
                            'profile': pos.profile,
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
    accounts = Account.objects.filter(
        account_name=sale.account.account_name, status=True, customer=None)
    if request.method == 'POST':
        if Sales.change_sale(request) == True:
            customer = sale.customer
            return Sales.render_view(request, customer)
    return render(request, template_name, {
        'customer': Sale.objects.get(pk=pk).customer,
        'sale': sale,
        'accounts': accounts,
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

class CuponView(UserAccessMixin, ListView):
    permission_required = 'is_staff'
    model = Cupon
    template_name = "adm/cupon.html"
    paginate_by = 15

@permission_required('is_staff', 'adm:no-permission')
def CuponRedeemView(request):
    template_name = "adm/cupon_redeem.html"
    error = None
    services = None
    if request.method == 'POST':
        cupon = request.POST.get('code').lower()
        customer = request.POST.get('customer')
        service = request.POST.get('service')
        if service:
            cupon = Cupon.objects.get(name=cupon)
            return render(request, template_name, {
                'service': service,
                'cupon': cupon,
                'customer': customer,
                'months': cupon.long
            })
        try:
            cupon = Cupon.objects.get(name=cupon)
            if cupon.customer:
                error = "El cupón ya fue utilizado"
            else:
                services = Service.objects.filter(status=True)
        except Cupon.DoesNotExist:
            error = "El cupón no existe"
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
        sale = Sales.cupon_sale(request)
        print(sale)
        if sale[0] == True:
            customer = User.objects.get(pk=customer)
            return Sales.render_view(request, customer)

class ReceivableView(UserAccessMixin, ListView):
    permission_required = 'is_staff'
    model = Sale
    template_name = "adm/receivable.html"
    paginate_by = 1000
    def get_queryset(self):
        if self.request.GET.get('date') is not None:
            return Sale.objects.filter(
                expiration_date__lte=f"{self.request.GET.get('date')} 23:59:59",
                expiration_date__gte=f"{self.request.GET.get('date')} 00:00:00",
                status=True
            ).order_by('-expiration_date', 'account')
        elif self.request.GET.get('email'):
            email = self.request.GET.get('email')
            if self.request.GET.get('date') is not None:
                exp_date = self.request.GET.get('date')
                return Sale.objects.filter(
                    expiration_date__gte=f'{exp_date} 00:00:00',
                    expiration_date__lte=f'{exp_date} 23:59:59',
                    status=True
                ).order_by('-expiration_date', 'account')
        else:
            return Sale.objects.filter(
                expiration_date__lte=f'{timezone.now().date()} 23:59:59',
                status=True
            ).order_by('-expiration_date', 'account__email')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tomorrow'] = timezone.now().date() + timedelta(days=1)
        context['left'] = Sale.objects.filter(
            expiration_date__lte=f'{timezone.now().date()} 23:59:59',
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
        data_release = Sale.objects.filter(account=acc, status=True, expiration_date__lte=datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999))
        data_report = Sale.objects.filter(account=acc, status=True, expiration_date__gte=datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999))
        if data_release:
            sales_to_release.append(data_release)
        if data_report:
            sales_to_report.append(data_report)
    for sales in sales_to_release:
        sales[0].status = False
        sales[0].save()
        message = f'Le informamos que su cuenta {sales[0].account.account_name.description} con email {sales[0].account.email} fue suspendida por falta de pago. Aún está a tiempo de recuperarla renovando su cuenta. Por favor, si tiene alguna duda o comentario solo escribe Hablar con un Humano o envianos un whats app al número de siempre. Saludos.'
        customer_detail_released = UserDetail.objects.get(user=sales[0].customer)
        Notification.send_whatsapp_notification(message, customer_detail_released.lada, customer_detail_released.phone_number)
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

        # Notificar a los clientes solo si cambió la contraseña
        if password_changed:
            for customer in sales_to_report:
                message = f'Le informamos que por su seguridad las claves de su cuenta {data_account.account_name} fueron cambiadas. A continuación le dejo sus nuevas claves:\n'
                message += f'Email: {email}\n'
                message += f'Contraseña: {password}\n'
                message += f'El perfil, pin y fechas de vencimiento siguen siendo los mismos.\n'
                message += f'Por favor, si tiene alguna duda o comentario solo escribe Hablar con un Humano o envianos un whats app al número de siempre. Saludos.'
                customer_detail = UserDetail.objects.get(user=customer[0].customer)
                # enviamos un request a un webhook solo si cambió la contraseña
                webhook_url = os.environ.get("N8N_WEBHOOK_URL_CHANGE_PASSWORD")
                # Convertir el objeto Service a string legible (usa .name o .description si existe)
                account_name_str = str(data_account.account_name)
                if hasattr(data_account.account_name, 'name'):
                    account_name_str = data_account.account_name.name
                elif hasattr(data_account.account_name, 'description'):
                    account_name_str = data_account.account_name.description
                payload = {
                    "account_name": account_name_str,
                    "email": email,
                    "password": password,
                    "message": message,
                    "lada": customer_detail.lada,
                    "phone_number": customer_detail.phone_number
                }
                if webhook_url:
                    requests.post(webhook_url, json=payload)
                Notification.send_whatsapp_notification(message, customer_detail.lada, customer_detail.phone_number)

        for a in acc:
            a.supplier = supplier
            a.modified_by = modified_by
            a.account_name = account_name
            a.expiration_date = expiration_date
            a.email = email
            a.password = password
            a.comments = comments
            a.renovable = renovable
            a.save()
            # Enviar notificación push solo si cambió la contraseña
            if password_changed:
                try:
                    sale_expiration = Sale.objects.get(
                        account=a.pk, customer=a.customer, status=True)
                    now = datetime.now()
                    if sale_expiration.expiration_date > now:
                        token = UserDetail.objects.get(user=a.customer).token
                        title = f"Las claves de tu {a.account_name} fueron actualizadas"
                        body = f"Visita la sección Mi Cuenta para ver las nuevas claves"
                        url = "MyAccount"
                        notification = send_push_notification(
                            token, title, body, url)
                except:
                    continue
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

from django.views.decorators.http import require_POST

@permission_required('is_staff', 'adm:no-permission')
@require_POST
def ActiveInactiveAccount(request, status, pk):
    account = Account.objects.get(pk=pk)
    # Convertir el string 'true'/'false' a booleano
    if isinstance(status, str):
        if status.lower() == 'true':
            new_status = True
        elif status.lower() == 'false':
            new_status = False
        else:
            new_status = account.status  # fallback
    else:
        new_status = bool(status)

    # Cambiar el estado a todas las cuentas con mismo account_name, email y password
    accounts_to_update = Account.objects.filter(
        account_name=account.account_name,
        email=account.email,
        password=account.password
    )
    accounts_to_update.update(status=new_status)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        # Respuesta para AJAX
        return JsonResponse({'success': True, 'new_status': new_status})
    return redirect(reverse('adm:accounts'))
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



# Scripts

def duplicate_account(request):
    account_name = Service.objects.get(id=21)
    # Search account to duplicate
    accounts = Account.objects.filter(account_name=account_name,status=True,expiration_date__gte = datetime.now())
    for account in accounts:
        print(account)
    return HttpResponse("listo")