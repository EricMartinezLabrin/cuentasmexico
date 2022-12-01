#Django
from django.shortcuts import render
from django.http import HttpResponse
from django.views.generic import CreateView
from django.contrib.auth.views import LoginView, LogoutView,PasswordResetView,PasswordResetDoneView,PasswordResetConfirmView, PasswordResetCompleteView
from django.contrib.auth.models import User,Group
from django.urls import reverse_lazy,reverse
from django.shortcuts import redirect

#local
from .forms import RegisterUserForm
from adm.models import UserDetail

#Python

#Index
def index(request):
    template_name="index/index.html"
    return render(request,template_name,{})


#Users Actions
class LoginPageView(LoginView):
    """
    Login a user and redirect to a verifier of permission on RedirectOnLoginView
    """
    template_name="index/login.html"
    model = User

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

class PassResetView(PasswordResetView):
    template_name = 'index/registration/password_reset_form.html'
    email_template_name = 'index/registration/password_reset_email.html'

class PassResetDoneView(PasswordResetDoneView):
    template_name = 'index/registration/password_reset_done.html'

class PassResetConfirmView(PasswordResetConfirmView):
    template_name = 'index/registration/password_reset_confirm.html'

class PassResetPasswordCompleteView(PasswordResetCompleteView):
    """
    Show message if password has correctly changed
    """
    template_name = 'index/registration/password_reset_complete.html'

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



