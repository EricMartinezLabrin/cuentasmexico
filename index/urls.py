# django
from django.urls import path
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView, PasswordResetCompleteView


from . import views


urlpatterns = [
    path('', views.index, name='index'),
    path('no-permission', views.NoPermissionView.as_view(), name='no-permission'),
    path('detail/<int:pk>', views.ServiceDetailView.as_view(), name='service_detail'),
    path('cart', login_required(views.CartView.as_view()), name='cart'),
    path('shop', views.ShopListView.as_view(), name='shop'),
    path('redeem', login_required(views.RedeemView.as_view()), name='redeem'),
    path('redeem/confirm', login_required(views.RedeemConfirmView.as_view()),
         name='redeem_confirm'),
    path('redeem/done', login_required(views.RedeemDoneView.as_view()),
         name='redeem_done'),
    path('redeem/done/renew', login_required(views.RedeemRenewDoneView.as_view()),
         name='redeem_done_renew'),
    path('select', login_required(views.SelectAccView.as_view()), name='select_acc'),
    path('checkout/<int:product_id>',
         views.CheckOutView.as_view(), name='checkout'),
    path('addCart/<int:product_id>/<int:price>', views.addCart, name='addCart'),
    path('removeCart/<int:product_id>', views.removeCart, name='removeCart'),
    path('decrementCart/<int:product_id>/<int:unitPrice>',
         views.decrementCart, name='decrementCart'),
    path('login', views.LoginPageView.as_view(
        redirect_authenticated_user=True), name='login'),
    path('logout', views.LogoutPageView.as_view(), name='logout'),
    path('register', views.RegisterCustomerView.as_view(), name='register'),
    path('redirect_on_login', views.RedirectOnLogin, name='redirect_on_login'),
    path('reset/password_reset',
         views.PassResetView.as_view(), name="password_reset"),
    path('reset/change_password',
         views.ChangePasswordView.as_view(), name="change_password"),
    path('reset/password_reset_done',
         views.PassResetDoneView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', views.PassResetConfirmView.as_view(),
         name='password_reset_confirm'),
    path('reset/done', views.PassResetPasswordCompleteView.as_view(),
         name='password_reset_complete'),
    path('email_update/<int:pk>', views.EmailUpdateView.as_view(),
         name='email_update'),
    path('email', views.SendEmail, name='email'),
    path('checkout/distributor', views.DistributorSale,
         name='checkout_distributor'),
    path('no_credits', views.NoCreditsView.as_view(), name='no_credits'),
    path('express-checkout/', views.MpWebhookUpdater, name='Mp_ExpressCheckout'),
    path('start_payment/',
         login_required(views.StartPayment), name='start_payment'),
    path('my_account/',
         login_required(views.MyAccountView.as_view()), name='my_account'),
    path('test/', views.test, name='test'),
]

