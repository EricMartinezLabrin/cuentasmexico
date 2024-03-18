# django
from django.urls import path
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView, PasswordResetCompleteView


from . import views

app_name = "ThanksYou"

urlpatterns = [
    path('system/<int:price>/<int:event_id>/', views.index, name='index'),
]

