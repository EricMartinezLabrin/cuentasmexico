#Django
import profile
from django.shortcuts import render
from django.http import HttpResponse,HttpRequest
from django.views.generic import DetailView, CreateView, UpdateView, TemplateView, ListView, DeleteView
from django.urls import reverse,reverse_lazy
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.models import User
from django.shortcuts import redirect
from django.core.paginator import Paginator
from django.http import JsonResponse


#Python
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import pyperclip as clipboard
import pandas as pd

#Local
from .models import Business, PaymentMethod, Sale,UserDetail,Service, Account, Bank, Status, Supplier
from cupon.models import Cupon
from .functions.alerts import Alerts
from .functions.forms import AccountsForm, BankForm, PaymentMethodForm, ServicesForm, SettingsForm, UserDetailForm, UserForm, FilterAccountForm, StatusForm, SupplierForm, CustomerUpdateForm,UserMainForm
from .functions.permissions import UserAccessMixin
from .functions.country import Country
from .functions.active_inactive import Active_Inactive
from .functions.dashboard import Dashboard
from adm.functions.duplicated import NoDuplicate
from adm.functions.sales import Sales
from adm.functions.import_data import ImportData

def is_ajax(request):
    return request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest'

@permission_required('is_superuser','adm:no-permission')
def index(request):
    """
    Main Admin Page
    """
    # sales = Dashboard.sales_per_country()
    template_name="adm/index.html"
    return render(request,template_name,{
        # 'sales':sales
    })

class NoPermissionView(TemplateView):
    """
    Page where are redirected users with out permissions
    """
    template_name = "adm/no_permission.html"

@permission_required('is_superuser','adm:no-permission')
def SettingsDetailView(request):
    """
    Here is displayed all Business Data
    """
    template_name = "adm/settings_details.html"
    try:
        business_detail = Business.objects.get(pk=1)
    except Business.DoesNotExist:
        business_detail = None

    return render(request,template_name,{
        'object':business_detail
    })

# @permission_required('is_superuser','adm:no-permission')
class SettingsCreateView(UserAccessMixin,CreateView):
    """
    Create Business Data once
    """
    permission_required = 'is_superuser'
    model = Business
    template_name = "adm/settings_update.html"
    form_class= SettingsForm
    success_url=reverse_lazy('adm:settings')

# @permission_required('is_superuser','adm:no-permission')
class SettingsUpdateView(UserAccessMixin,UpdateView):
    """
    Update Business Data
    """
    permission_required = 'is_superuser'
    model = Business
    template_name = "adm/settings_update.html"
    form_class= SettingsForm
    success_url=reverse_lazy('adm:settings')  

@permission_required('is_staff','adm:no-permission')
def ProfileView(request):
    """
    Show all user info
    """
    template_name = "adm/profile_details.html"
    return render(request,template_name,{
    })

class UserdetailUpdateView(UserAccessMixin,UpdateView):
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

class CustomerUpdateView(UserAccessMixin,UpdateView):
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
    
class UserUpdateView(UserAccessMixin,UpdateView):
    """
    Update data and profile picture of users
    """
    permission_required = 'is_staff'
    model = User
    template_name = "adm/profile_update.html"
    form_class= UserForm
    success_url = reverse_lazy('adm:profile')

class MainUserUpdateView(UserAccessMixin,UpdateView):
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

class ServiceView(UserAccessMixin,ListView):
    """
    Here you can see all Available Services
    """
    permission_required= 'is_staff'
    model=Service
    template_name = 'adm/services.html'

class ServiceCreateView(UserAccessMixin,CreateView):
    """
    Create a new service
    """
    permission_required='is_staff'
    model = Service
    template_name = "adm/services_create.html"
    form_class= ServicesForm
    success_url = reverse_lazy('adm:services')

class ServiceUpdateView(UserAccessMixin,UpdateView):
    model = Service
    permission_required='is_staff'
    template_name = "adm/services_create.html"
    form_class = ServicesForm
    success_url = reverse_lazy('adm:services')

class ServiceDeleteView(UserAccessMixin,DeleteView):
    model = Service
    permission_required='is_staff'
    template_name = "adm/delete.html"
    success_url = reverse_lazy('adm:services')

@permission_required('is_staff','adm:no-permission')
def ActiveInactiveService(request,status,pk):
    service = Service.objects.get(pk=pk)
    service.status = Active_Inactive.active_inactive(status)
    service.save()
    return redirect(reverse('adm:services'))

@permission_required('is_staff','adm:no-permission')
def AccountsView(request):
    """
    Show all active accounts filtered by Bussiness ID of person are looking for And Pagintate by 10
    """
    business_id = request.user.userdetail.business
    template_name = 'adm/accounts.html'
    form = FilterAccountForm()
    today = datetime.now().date()
    if request.method == 'POST':
        account_name=request.POST['account_name']
        email = request.POST['email'].replace(" ","")
        status = request.POST['status']
        if not email:
            if not status:
                accounts = Account.objects.filter(
                business= business_id,
                account_name=account_name
                )
            else:
                accounts = Account.objects.filter(
                business= business_id,
                account_name=account_name,
                status=status
                )
        else:
            if not status:
                accounts = Account.objects.filter(
                    business= business_id,
                    account_name=account_name,
                    email=email,
                    )  
            else:
                accounts = Account.objects.filter(
                    business= business_id,
                    account_name=account_name,
                    email=email,
                    status=status
                    )
            #Set Up Pagination
        p =Paginator(accounts, 10000)
        page = request.GET.get('page')
        venues = p.get_page(page)
        return render(request, template_name,{
            "accounts": accounts,
            "venues": venues,
            "form": form,
            "today": today
        })
    else:
        active = 1
        accounts = Account.objects.filter(status=active, business= business_id, customer= None).order_by('account_name','email','profile','expiration_date')
            #Set Up Pagination
        p =Paginator(accounts, 7)
        page = request.GET.get('page')
        venues = p.get_page(page)
        return render(request, template_name,{
            "accounts": accounts,
            "venues": venues,
            "form": form,
            "today":today
        })

@permission_required('is_staff','adm:no-permission')
def AccountsCreateView(request):
    """
    Create a new Account
    """
    template_name='adm/accounts_create.html'
    form_class = AccountsForm(request.POST or None)
    success_url = reverse_lazy('adm:accounts')

    if request.method == 'POST':
        business = Business.objects.get(pk=request.POST.get('business'))
        supplier = Supplier.objects.get(pk=request.POST.get('supplier'))
        created_by = User.objects.get(pk=request.POST.get('created_by'))
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
        profile = account_name.perfil_quantity
        for i in range(profile+1):
            if i == 0:
                continue
            Account.objects.create(
                business = business,
                supplier = supplier,
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
        return render(request,template_name,{
            'form': form_class
        })

@permission_required('is_staff','adm:no-permission')
def AccountsUpdateView(request,pk):
    """
    Create a new Account
    """
    template_name='adm/accounts_create.html'
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
        if request.POST.get('renovable') == 'on':
            renovable = True
        else:
            renovable = False
        
        old = Account.objects.get(pk=pk)
        acc = Account.objects.filter(
            account_name=old.account_name,
            email=old.email
        )
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
        return redirect(success_url)
    else:
        return render(request,template_name,{
            'form': form_class
        })

@permission_required('is_staff','adm:no-permission')
def AccountsExpiredView(request):
    """
    Show all active accounts filtered by Bussiness ID of person are looking for, expiration date And Pagintate by 10
    """
    business_id = request.user.userdetail.business
    template_name = 'adm/accounts_expired.html'
    today = datetime.now().date()

    form = FilterAccountForm()
    if request.method == 'POST':
        date = request.POST['vencimiento'].replace(" ","")
        status = request.POST['status']
        if not date:
            if not status:
                accounts = Account.objects.filter(
                    business= business_id,
                    expiration_date__lte = today
                    )   
            else:
                accounts = Account.objects.filter(
                business= business_id,
                status=status,
                expiration_date__lte = today
                )          
        else:
            if not status:
                accounts = Account.objects.filter(
                    business= business_id,
                    expiration_date = date
                    )   
            else:
                accounts = Account.objects.filter(
                    business= business_id,
                    status=status,
                    expiration_date = date
                    )
            #Set Up Pagination
        accounts = NoDuplicate.no_duplicate(accounts)
        p =Paginator(accounts, 10000)
        page = request.GET.get('page')
        venues = p.get_page(page)
        return render(request, template_name,{
            "accounts": accounts,
            "venues": venues,
            "form": form
        })
    else:
        active = 1
        accounts = Account.objects.filter(business= business_id, expiration_date__lte = today)
        acc = NoDuplicate.no_duplicate(accounts)

            #Set Up Pagination
        p =Paginator(acc, 7)
        page = request.GET.get('page')
        venues = p.get_page(page)
        return render(request, template_name,{
            "accounts": accounts,
            "venues": venues,
            "form": form
        })

@permission_required('is_staff','adm:no-permission')
def ActiveInactiveAccount(request,status,pk):
    active = Status.objects.get(description='Activo')
    inactive = Status.objects.get(description='Inactivo')
    account = Account.objects.get(pk=pk)
    account.status = Active_Inactive.active_inactive(status)
    account.save()
    return redirect(reverse('adm:accounts'))

@permission_required('is_staff','adm:no-permission')
def SalesView(request):
    template_name='adm/sale.html'

    if request.method == 'POST':
        try:
            customer = Sales.is_email(request,request.POST.get('customer'))
        except NameError:
            message = "Número de telefono invalido, tiene más carácteres de los permitidos."
            return Sales.render_view(request,message=message)
        except TypeError:
            message = 'El email ingresado no tiene el formato correcto, debe incluir "@"'
            return Sales.render_view(request,message=message)

        if customer == 'phone':
            template_name = 'adm/user_new_customer.html'
            customer = request.POST.get('customer').replace(" ","")
            if request.POST.get('new-customer') == 'yes':
                customer = request.POST.get('customer')
                user = User.objects.create_user(customer, 'example@example.com', 'cuentasmexico')
                user_detail = UserDetail.objects.create(business=request.user.userdetail.business,user=user,phone_number=int(customer),lada=0,country="??")
                return redirect(reverse('adm:user_reference',args=(user_detail.id,)))
            return render (request,template_name,{
                'customer': customer
            })
        if customer == 'email':
            template_name = 'adm/user_new_customer.html'
            customer = request.POST.get('customer').replace(" ","")
            if request.POST.get('new-customer') == 'yes':
                customer = request.POST.get('customer')
                user = User.objects.create_user(customer, customer, 'cuentasmexico')
                user_detail = UserDetail.objects.create(business=request.user.userdetail.business,user=user,phone_number=0,lada=0,country="??")
                return redirect(reverse('adm:user_reference',args=(user_detail.id,)))
            return render (request,template_name,{
                'customer': customer
            })
        try:
            customer.country
            # return redirect(reverse('adm:user_update',args=(customer.id,)))
            return redirect(reverse('adm:user_reference',args=(customer.id,)))
        except AttributeError:
            return Sales.render_view(request,customer.id)

    else:
        return render(request,template_name,{
            'availables': Sales.availables()[0]
        })

def SalesAddFreeDaysView(request,pk,days):
    sale = Sale.objects.get(pk=pk)
    new_expiration = sale.expiration_date + timedelta(days=days)
    sale.expiration_date = new_expiration
    sale.save()
    customer = UserDetail.objects.get(user=sale.customer.id)
    customer.free_days = 0
    customer.save()
    print(customer.free_days)
    return Sales.render_view(request,sale.customer.id)

@permission_required('is_staff','adm:no-permission')
def UserReferenceView(request,pk):
    template_name="adm/user_reference.html"
    customer_reference = pk
    message = ''

    if request.method=='POST':
        reference_phone = request.POST.get('reference')
        try:
            user = UserDetail.objects.get(phone_number=reference_phone)
            
            user.free_days+=7
            user.reference_used=False
            user.save()
            
            customer = UserDetail.objects.get(pk=pk)
            customer.free_days+=7
            customer.reference=user.id
            customer.reference_used=False
            print('si entro')
            customer.save()
            return redirect(reverse('adm:user_update',args=(pk,)))

        except UserDetail.DoesNotExist:
            message = "El cliente ingresado no existe"

    return render(request,template_name,{
        'customer_reference':customer_reference,
        'pk':pk,
        'message':message
    })

@permission_required('is_staff','adm:no-permission')
def SalesCreateView(request,pk):
    template_name = 'adm/sale_create.html'
    bank = Bank.objects.filter(status=True)
    payment = PaymentMethod.objects.all()
    
    if request.method == 'POST':
        if Sales.new_sale(request) == True:
            customer = User.objects.get(pk=pk)
            return Sales.render_view(request,customer)

    return render(request,template_name,{
        'customer': User.objects.get(pk=pk),
        'services': Sales.availables()[1],
        'bank':bank,
        'payment':payment,
        'availables': Sales.availables()[0]
    })

@permission_required('is_staff','adm:no-permission')
def SalesUpdateStatusView(request,pk,customer,status):
    sale = Sale.objects.get(pk=pk)
    sale.status = Active_Inactive.active_inactive(status)
    sale.expiration_date = datetime.now()
    sale.save()
    acc = sale.account
    acc.customer = None
    acc.save()
    return Sales.render_view(request,customer)

@permission_required('is_staff','adm:no-permission')
def SalesSearchView(request):
    if is_ajax(request):
        res = None
        services = request.POST.getlist('data[]','')
        data = []
        if services:
            for s in services:
                service = Service.objects.get(pk=s)
                acc = Account.objects.filter(account_name=service,customer=None,status=True).order_by('-expiration_date')
                if len(acc)>0 and len(services) > 0:
                    for pos in acc:
                        item ={
                            'id':pos.id,
                            'logo':str(pos.account_name.logo),
                            'acc_name': pos.account_name.description,
                            'email': pos.email,
                            'password': pos.password,
                            'expiration_acc': pos.expiration_date,
                            'profile':pos.profile

                        }
                        data.append(item)
                    res = data
                else:
                    res = "No hay cuentas disponibles"

            return JsonResponse({'data':res})
        else:
            res = "No hay cuentas seleccionadas"
        return JsonResponse({'data':res})
    return JsonResponse({})

@permission_required('is_staff','adm:no-permission')
def SalesSearchDetailView(request):
    if is_ajax(request):
        res = None
        services = request.POST.getlist('det[]','')
        data = []
        if services:
            for s in services:
                account = Account.objects.get(pk=s)
                det = Account.objects.filter(account_name=account.account_name,email=account.email, password=account.password)
                print(account.id)
                if len(det)>0 and len(services) > 0:
                    for pos in det:
                        # try:
                        customer_end_date = Sale.objects.filter(account=pos.id,customer=pos.customer)#.expiration_date
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
                            customer = User.objects.get(pk=pos.customer.id).userdetail.phone_number
                        else:
                            customer = None
                        
                        # 
                        item ={
                            'id':pos.id,
                            'logo':str(pos.account_name.logo),
                            'email':pos.email,
                            'profile':pos.profile,
                            'customer':customer,
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
            return JsonResponse({'det':det})
        else:
            det = "No hay cuentas seleccionadas"
        return JsonResponse({'det':det})
    return JsonResponse({})

@permission_required('is_staff','adm:no-permission')
def RenewView(request,pk):
    template_name='adm/sales_renew.html'
    sale = Sale.objects.get(pk=pk)
    banklist = Bank.objects.filter(status=True)
    paymentmethodlist = PaymentMethod.objects.all()
    if request.method == 'POST':
        if Sales.renew_sale(request,pk) == True:
            customer = Sale.objects.get(pk=pk).customer
            return Sales.render_view(request,customer)            

    return render(request,template_name,{
        'object':sale,
        'banklist':banklist,
        'paymentmethodlist':paymentmethodlist
    })

@permission_required('is_staff','adm:no-permission')
def SalesChangeView(request,pk):
    template_name = 'adm/sale_change.html'
    bank = Bank.objects.filter(status=True)
    payment = PaymentMethod.objects.all()
    sale = Sale.objects.get(pk=pk)
    accounts = Account.objects.filter(account_name=sale.account.account_name, status=True,customer=None)

    
    if request.method == 'POST':
        if Sales.change_sale(request) == True:
            customer = sale.customer
            return Sales.render_view(request,customer)

    return render(request,template_name,{
        'customer': Sale.objects.get(pk=pk).customer,
        'sale':sale,
        'accounts': accounts,
        'availables': Sales.availables()[0]
    })

def SalesCopyPass(request,sale_id):
    sale = Sale.objects.get(pk=sale_id)
    
    #Set as sent
    account = sale.account
    account.sent = True
    account.save()

    if sale.account.pin:
        pin = f'\n*Pin:* {sale.account.pin}'
    else:
        pin = ""

    message = f'*E-Mail:* {sale.account.email} \n*Clave:* {sale.account.password}  {pin} \n*Perfil:* {sale.account.profile} \n\n💎 Esta es su cuenta *{sale.account.account_name.description}* para *1 Dispositivo*. Inicie sesión con el *EMAIL* y *CLAVE* recibida \n💎 Usar *SOLO EL PERFIL ASIGNADO* \n💎 *NO* puedes cambiar las claves. Gracias por tu preferencia, Recuerde que los unicos canales oficiales de atecion son: Whats App y Telegram al número 833 535 5863.'

    # clipboard.copy("message")
    #df=pd.DataFrame([message])
    #df.to_clipboard(index=False,header=False)

    return Sales.render_view(request,customer=sale.customer,copy=message)

def OldAccView(request,sale):
    template_name = 'adm/archive.html'
    sale_data = Sale.objects.get(pk=sale)
    new_data = Sale.objects.get(pk=sale_data.old_acc)
    return render(request,template_name,{
        'data':sale_data,
        'new_data': new_data
    })

def CheckTicket(request):
    if is_ajax(request):
        data = None
        ticket = request.POST.get('data')
        used = Sale.objects.filter(invoice=ticket)
        if used:
            data=[]
            for u in used:
                my_dict={
                    'email':u.account.email,
                    'customer':u.customer.userdetail.phone_number,
                    'date':u.created_at,
                    'ticket':u.invoice
                }
                data.append(my_dict)
            return JsonResponse({'data':data})
        else:
            return JsonResponse({'data':data})

class ProfileUpdateView(UserAccessMixin,UpdateView):
    """
    Update aprofile number
    """
    permission_required='is_staff'
    model = Account
    template_name = "adm/accounts_profile.html"
    success_url = reverse_lazy('adm:accounts')
    fields = ['profile']

class BankListView(UserAccessMixin,ListView):
    """
    Show all bank accounts
    """
    permission_required='is_staff'
    model = Bank
    template_name = "adm/bank.html"

class bankCreateView(UserAccessMixin,CreateView):
    """
    Create a new Bank Account
    """
    permission_required='is_staff'
    model = Bank
    template_name = "adm/bank_create.html"
    success_url = reverse_lazy('adm:bank')
    form_class = BankForm

class BankUpdateView(UserAccessMixin,UpdateView):
    """
    Update a existent bank account
    """
    permission_required='is_staff'
    model = Bank
    template_name = "adm/bank_create.html"
    success_url = reverse_lazy('adm:bank')
    form_class = BankForm

class BankDeleteView(UserAccessMixin,DeleteView):
    """
    Delete a Bank Account
    """
    permission_required='is_staff'
    model = Bank
    template_name = "adm/delete.html"
    success_url = reverse_lazy('adm:bank')

class PaymentMethodListView(UserAccessMixin,ListView):
    """
    Show all payment methods
    """
    permission_required='is_staff'
    model = PaymentMethod
    template_name = "adm/payment_method.html"

class PaymentMethodCreateView(UserAccessMixin,CreateView):
    """
    Create a new Payment Method
    """
    permission_required='is_staff'
    model = PaymentMethod
    template_name = "adm/payment_method_create.html"
    success_url = reverse_lazy('adm:payment_method')
    form_class = PaymentMethodForm

class PaymentMethodUpdateView(UserAccessMixin,UpdateView):
    """
    Update a existent Payment Method
    """
    permission_required='is_staff'
    model = PaymentMethod
    template_name = "adm/payment_method_create.html"
    success_url = reverse_lazy('adm:payment_method')
    form_class = PaymentMethodForm

class PaymentMethodDeleteView(UserAccessMixin,DeleteView):
    permission_required='is_staff'
    model = PaymentMethod
    template_name = "adm/delete.html"
    success_url = reverse_lazy('adm:payment_method')

class StatusListView(UserAccessMixin,ListView):
    permission_required='is_staff'
    model = Status
    template_name = "adm/status.html"

class StatusCreateView(UserAccessMixin,CreateView):
    permission_required='is_staff'
    model = Status
    template_name = "adm/status_create.html"
    success_url = reverse_lazy('adm:status')
    form_class = StatusForm

class StatusUpdateView(UserAccessMixin,UpdateView):
    permission_required='is_staff'
    model = Status
    template_name = "adm/status_create.html"
    success_url = reverse_lazy('adm:status')
    form_class = StatusForm

class StatusDeleteView(UserAccessMixin,DeleteView):
    permission_required='is_staff'
    model = Status
    template_name = "adm/delete.html"
    success_url = reverse_lazy('adm:status')

class SupplierListView(UserAccessMixin,ListView):
    permission_required='is_staff'
    model = Supplier
    template_name = "adm/supplier.html"

class SupplierCreateView(UserAccessMixin,CreateView):
    permission_required='is_staff'
    model = Supplier
    template_name = "adm/supplier_create.html"
    success_url = reverse_lazy('adm:supplier')
    form_class = SupplierForm

class SupplierUpdateView(UserAccessMixin,UpdateView):
    permission_required='is_staff'
    model = Supplier
    template_name = "adm/supplier_create.html"
    success_url = reverse_lazy('adm:supplier')
    form_class = SupplierForm

class SupplierDeleteView(UserAccessMixin,DeleteView):
    permission_required='is_staff'
    model = Supplier
    template_name = "adm/delete.html"
    success_url = reverse_lazy('adm:supplier')

class CuponView(UserAccessMixin,ListView):
    permission_required='is_staff'
    model = Cupon
    template_name = "adm/cupon.html"
    paginate_by = 15

@permission_required('is_staff','adm:no-permission')
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
            return render(request,template_name,{
            'service': service,
            'cupon':cupon,
            'customer':customer
        })
        try:
            cupon = Cupon.objects.get(name=cupon)
            if cupon.customer:
                error = "El cupón ya fue utilizado"
            else:
                services = Service.objects.filter(status=True)
        except Cupon.DoesNotExist:
            error = "El cupón no existe"

        return render(request,template_name,{
            'error': error,
            'services': services,
            'cupon':cupon,
            'customer':customer
        })

@permission_required('is_staff','adm:no-permission')
def CuponRedeemEndView(request):
    if request.method == 'POST':
        customer = request.POST.get('customer')
        if Sales.cupon_sale(request) == True:
            customer = User.objects.get(pk=customer)
            return Sales.render_view(request,customer)

class ReceivableView(UserAccessMixin,ListView):
    permission_required='is_staff'
    model = Sale
    template_name = "adm/receivable.html"
    paginate_by = 10
    
    def get_queryset(self):
        if self.request.GET.get('date') is not None:
            return Sale.objects.filter(
            expiration_date = self.request.GET.get('date'), 
            status=True
        ).order_by('account')

        else:
            return Sale.objects.filter(
                expiration_date = '2022-11-30', 
                status=True
            ).order_by('account')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tomorrow'] = datetime.now().date() + timedelta(days=1)
        context['left'] = Sale.objects.filter(
            expiration_date = '2022-11-30',
            status=True
        ).count()
        return context

@permission_required('is_staff','adm:no-permission')
def ReceivableCopyPass(request,sale_id):
    sale = Sale.objects.get(pk=sale_id)
    
    message = f'Buenas tardes amig@, le recuerdo que su cuenta  {sale.account.account_name} ya venció, para seguir utilizándola debe renovar. Por ser cliente frecuente tendrás un 10% de descuento si renuevas por 3 meses o más el día de hoy.'

    clipboard.copy(message)

    return redirect(reverse('adm:receivable'))

@permission_required('is_staff','adm:no-permission')
def ReleaseAccounts(request,pk):
    template_name = 'adm/accounts_create.html'
    success_url = reverse('adm:receivable')
    sale = Sale.objects.get(pk=pk)
    
    #Change Sale Status
    sale.status = False
    sale.save()

    #ReleaseProfile
    account = sale.account
    account.customer = None
    account.modified_by = request.user
    account.save()

    #Update Password
    form_class = AccountsForm(request.POST or None,instance=account)

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
        
        old = Account.objects.get(pk=account.id)
        acc = Account.objects.filter(
            account_name=old.account_name,
            email=old.email
        )
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
        return redirect(success_url)      

    return render(request,template_name,{
        'form':form_class
    })



@permission_required('is_staff','adm:no-permission')
def ImportView(request):
    #ImportData.services()
    #ImportData.customers()
    #ImportData.accounts(request)
    #ImportData.sales(request)
    #ImportData.bank()
    #ImportData.invoices()
    #ImportData.update_country()
    ImportData.shop()
    ImportData.cupon()
    return redirect(reverse('adm:index'))




    

    
    
    



