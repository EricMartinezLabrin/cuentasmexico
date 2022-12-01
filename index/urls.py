#django
from django.urls import path
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView,PasswordResetView,PasswordResetDoneView,PasswordResetConfirmView, PasswordResetCompleteView


from . import views


urlpatterns = [
    path('',views.index,name='index'),
    path('login',views.LoginPageView.as_view(redirect_authenticated_user=True),name='login'),
    path('logout',views.LogoutPageView.as_view(),name='logout'),
    path('register',views.RegisterCustomerView.as_view(),name='register'),
    path('redirect_on_login',views.RedirectOnLogin,name='redirect_on_login'),
    path('reset/password_reset',views.PassResetView.as_view(),name="password_reset"),
    path('reset/password_reset_done',views.PassResetDoneView.as_view(),name='password_reset_done'),
    path('reset/<uidb64>/<token>/',views.PassResetConfirmView.as_view(),name='password_reset_confirm'),
    path('reset/done',views.PassResetPasswordCompleteView.as_view(),name='password_reset_complete'),
]