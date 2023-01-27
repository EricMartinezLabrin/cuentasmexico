#Django
from django.shortcuts import render
from django.http import HttpResponse
from django.contrib.auth.views import LoginView, LogoutView,PasswordResetView,PasswordResetDoneView,PasswordResetConfirmView, PasswordResetCompleteView
from django.contrib.auth.models import User,Group
from django.urls import reverse_lazy,reverse
from django.shortcuts import redirect
from django.views.generic import DetailView,CreateView,TemplateView,ListView
from django.views.generic.edit import FormView
from django.http import HttpResponseRedirect
from django.contrib.auth.decorators import permission_required
from django.utils import timezone

#local
from .forms import RegisterUserForm, RedeemForm
from adm.models import UserDetail, Business, Service,Sale, Account
from adm.functions.business import BusinessInfo
from .cart import CartProcessor
from cupon.models import Shop, Cupon
from adm.functions.permissions import UserAccessMixin
from adm.functions.sales import Sales
from adm.functions.send_email import Email

#Python
from datetime import datetime, timedelta
from dateutil import relativedelta

#Index
def index(request):
    template_name="index/index.html"
    services = Service.objects.filter(status=True)

    return render(request,template_name,{
        'business':BusinessInfo.data(),
        'credits': BusinessInfo.credits(request),
        'services': services,
    })

class CartView(TemplateView):
    template_name = "index/cart.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["business"] =  BusinessInfo.data()
        context["credits"] = BusinessInfo.credits(self.request)
        return context
    
class CheckOutView(TemplateView):
    template_name = "index/checkout.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["business"] =  BusinessInfo.data()
        context["credits"] = BusinessInfo.credits(self.request)
        return context

class ServiceDetailView(DetailView):
    model = Service
    template_name = 'index/service_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["count"] = BusinessInfo.count_sales(self.kwargs['pk'])
        return context

class ShopListView(ListView):
    model = Shop
    template_name = "index/shop.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["business"] =  BusinessInfo.data()
        context["credits"] = BusinessInfo.credits(self.request)
        return context
    
    def get_queryset(self):
        if self.request.GET.get('city') is not None:
            city = self.request.GET.get('city')
            try:
                return Shop.objects.filter(city=city).exclude(status=False)
            except Shop.DoesNotExist:
                return None
        else:
            return super().get_queryset().exclude(status=False)

class RedeemView(UserAccessMixin,FormView):
    permission_required = 'customer'
    template_name = "index/redeem.html"
    form_class = RedeemForm
    success_url = reverse_lazy('redeem')
    customer = None

    def get_code(self):
        if self.request.GET.get('name'):
            code = self.request.GET.get('name')
            code = Cupon.objects.get(name=code)
            return code
        else:
            code = None

    def get_active_acc(self):
        if self.request.user:
            user = self.request.user
            active_acc = Sale.objects.filter(customer=user,status=True)
            return active_acc
    
    def get_error(self):
        error = None
        if self.get_code():
            if self.get_code().customer:
                error = "El código ya fue utilizado, si no lo canjeó usted, porfavor, contacte a su vendedor y pidale uno nuevo."
        
        return error

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["business"] =  BusinessInfo.data()
        context["credits"] = BusinessInfo.credits(self.request)
        context["error"] = self.get_error()
        context["code"] = self.get_code()
        context["customer_data"] = self.get_active_acc()
        return context

class SelectAccView(TemplateView):
    template_name = "index/select_acc.html"
    code = None
    error = None

    def get_code(self):
        if self.request.GET.get('name'):
            code = self.request.GET.get('name')
            code = Cupon.objects.get(name=code)
            return code

    def get_availables(self):
        available = Service.objects.filter(status=True)
        return available
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["business"] =  BusinessInfo.data()
        context["credits"] = BusinessInfo.credits(self.request)
        context["error"] = self.error
        context["code"] = self.get_code()
        context["available"] = self.get_availables()
        return context

class RedeemConfirmView(TemplateView):
    template_name = "index/redeem_confirm.html"
    code = None
    error = None

    def get_code(self):
        if self.request.GET.get('name'):
            code = self.request.GET.get('name')
            code = Cupon.objects.get(name=code)
            return code
    
    def account(self):
        if self.request.GET.get('service'):
            try:
                account = Service.objects.get(pk=self.request.GET.get('service'))
            except Service.DoesNotExist:
                account = Account.objects.get(pk=self.request.GET.get('service'))
            return account
    
    def get_error(self):
        if self.get_code().customer:
            if self.get_code().status == False:
                return "Error. El código ya fue utilizado, si no lo canjeó usted contacte a su vendedor y pidale uno nuevo."
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["error"] = self.get_error
        context["code"] = self.get_code()
        context["account"] = self.account()
        return context

class RedeemRenewDoneView(TemplateView):
    template_name = "index/redeem_done.html"

    def complete_redeem(self):
        code = self.request.GET.get('name')
        service_id = self.request.GET.get('service')
        service = Account.objects.get(pk = service_id)
        customer = self.request.user.id
        
        renew = Sales.redeem_renew(self.request,service,code,customer)

        return renew
    
    def get_code(self):
        if self.request.GET.get('name'):
            code = self.request.GET.get('name')
            try:
                code = Cupon.objects.get(name=code)
            except Cupon.DoesNotExist:
                code = None
            return code

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["business"] =  BusinessInfo.data()
        context["credits"] = BusinessInfo.credits(self.request)
        context["account"] =  self.complete_redeem()
        context["code"] = self.get_code()
        return context


class RedeemDoneView(TemplateView):
    template_name = "index/redeem_done.html"

    def complete_redeem(self):
        code = self.request.GET.get('name')
        service_id = self.request.GET.get('service')
        try:
            cupon = Cupon.objects.get(name=code)
            start_date = timezone.now()
            end_date = start_date + timedelta(days=cupon.long*31)
            customer = self.request.user.id
            
            if not cupon.customer:
                account = Sales.search_better_acc(service_id,end_date,code)
            else:
                account = (False,"Error. El código ya fue utilizado, si no lo canjeó usted contacte a su vendedor y pidale uno nuevo.")

            if account[0] == True:
                Sales.redeem(self.request,account[1],code,customer)
            return account
        except Cupon.DoesNotExist:
            return False,"El código no existe, porfavor contacte a su vendedor y pidale uno nuevo."


    def get_code(self):
        if self.request.GET.get('name'):
            code = self.request.GET.get('name')
            try:
                code = Cupon.objects.get(name=code)
            except Cupon.DoesNotExist:
                code = None
            return code

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["business"] =  BusinessInfo.data()
        context["credits"] = BusinessInfo.credits(self.request)
        context["account"] =  self.complete_redeem()
        context["code"] = self.get_code()
        return context


#Cart
def addCart(request,product_id,price):
    cart = CartProcessor(request)
    service = Service.objects.get(pk=product_id)
    if request.method == 'POST':
        quantity = int(request.POST.get('quantity'))
        profiles = int(request.POST.get('profiles'))
        price_unit = int(request.POST.get('price'))
        cart.add(product=service,quantity=quantity,profiles=profiles,price=price_unit)
        return HttpResponseRedirect(reverse("cart"))
    cart.add(service,1,1,price)  
    return HttpResponseRedirect(reverse("cart"))

def removeCart(request,product_id):
    cart = CartProcessor(request)
    service = Service.objects.get(pk=product_id)
    cart.remove(service)  
    return HttpResponseRedirect(reverse("cart"))

def decrementCart(request,product_id, unitPrice):
    cart = CartProcessor(request)
    service = Service.objects.get(pk=product_id)
    cart.decrement(service,unitPrice)  
    return HttpResponseRedirect(reverse("cart"))


#Users Actions
class LoginPageView(LoginView):
    """
    Login a user and redirect to a verifier of permission on RedirectOnLoginView
    """
    template_name="index/login.html"
    model = User

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["business"] =  BusinessInfo.data()
        context["credits"] = BusinessInfo.credits(self.request)
        return context

class LogoutPageView(LogoutView):
    """
    Log Out User
    """
    pass

class RegisterCustomerView(CreateView):
    """
    Register new customers and redirect to main page
    """
    model = User
    template_name = "index/register.html"
    form_class = RegisterUserForm
    success_url = reverse_lazy("index")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["business"] =  BusinessInfo.data()
        context["credits"] = BusinessInfo.credits(self.request)
        return context

class PassResetView(PasswordResetView):
    template_name = 'index/registration/password_reset_form.html'
    email_template_name = 'index/registration/password_reset_email.html'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["business"] =  BusinessInfo.data()
        context["credits"] = BusinessInfo.credits(self.request)
        return context

class PassResetDoneView(PasswordResetDoneView):
    template_name = 'index/registration/password_reset_done.html'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["business"] =  BusinessInfo.data()
        context["credits"] = BusinessInfo.credits(self.request)
        return context

class PassResetConfirmView(PasswordResetConfirmView):
    template_name = 'index/registration/password_reset_confirm.html'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["business"] =  BusinessInfo.data()
        context["credits"] = BusinessInfo.credits(self.request)
        return context

class PassResetPasswordCompleteView(PasswordResetCompleteView):
    """
    Show message if password has correctly changed
    """
    template_name = 'index/registration/password_reset_complete.html'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["business"] =  BusinessInfo.data()
        context["credits"] = BusinessInfo.credits(self.request)
        return context

def RedirectOnLogin(request):
    """
    Verify permission and details of User and redirect to Main Page or Admin Page
    """
    #Verify Details
    try:
        details = UserDetail.objects.get(user_id=request.user.id)
    except UserDetail.DoesNotExist:
        UserDetail.objects.create(phone_number=0,lada=0,country="",business_id=1,user_id=request.user.id)

    group = request.user.groups.all()
    print(f'Pertenece al grupo {group}')
    #If no have any group
    if not request.user.groups.all():
        #asign Customer Group
        group = Group.objects.get(name='Customer')
        user = User.objects.get(pk=request.user.id)
        user.groups.add(group)
        #Redirect to shop
        template_name = 'index'
        print('Es Cliente')
    else:
        template_name = 'adm:index'
        print('Es Trabajador')

    return redirect(reverse(template_name))

class NoPermissionView(TemplateView):
    """
    Page where are redirected users with out permissions
    """
    template_name = "index/no_permission.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["business"] =  BusinessInfo.data()
        context["credits"] = BusinessInfo.credits(self.request)
        return context


def SendEmail(request):
    template_name = "index/email.html"
    acc = Sale.objects.filter(pk__lte=3)

    if request.method == 'POST':
        Email.email_passwords(request,'contacto@cuentasmexico.mx',acc)

    return render(request,template_name,{})

def DistributorSale(request):
    cart = request.session.get('cart_number')
    total = request.session.get('cart_total')
    credits_availables = BusinessInfo.credits(request)
    #check if enoght credits
    if credits_availables < total:
        return HttpResponse("Error, no cuentas con creditos suficientes")

    for key,values in cart.items():
        print(values)
    return HttpResponse("Todo Bien")
    