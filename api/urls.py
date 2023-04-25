# django
from django.urls import path
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView, PasswordResetCompleteView


from . import views

app_name="api"

urlpatterns = [
    path('login_api/<str:username>/<str:password>', views.loginApi, name='login_api'),
    path('get_active_accounts', views.getActiveAccounts, name='get_active_accounts')
]