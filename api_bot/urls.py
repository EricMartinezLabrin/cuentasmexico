# django
from django.urls import path
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView, PasswordResetCompleteView


from . import views

app_name = "api_bot"

urlpatterns = [
path('get_active_sales_by_user_api/<str:customer>/', views.get_active_sales_by_user_api, name='get_active_sales_by_user_api'),
]
