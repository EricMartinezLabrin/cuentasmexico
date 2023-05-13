# django
from django.urls import path
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView, PasswordResetCompleteView


from . import views

app_name = "api"

urlpatterns = [
    path('login_api/<str:username>/<str:password>',
         views.loginApi, name='login_api'),
    path('get_active_accounts', views.getActiveAccounts,
         name='get_active_accounts'),
    path('set_token', views.setToken, name='set_token'),
    path('send_notification', views.sendNotification, name='send_notification'),
    path('getServices', views.getServices, name='getServices'),
    # path('checkFlowPaymentByTokenApi', views.checkFlowPaymentByTokenApi, name='checkFlowPaymentByTokenApi'),
    path('stripe/create_payment/',
         views.stripe_create_payment, name='create_payment'),
    path('get_keys', views.get_keys, name='get_keys'),
    path('saleApi', views.saleApi, name='saleApi'),
    path('get_services_by_name_api/<str:name>',
         views.get_services_by_name_api, name='get_services_by_name_api'),
    path('create_user_api', views.create_user_api, name='create_user_api'),
]
