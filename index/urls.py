# django
from django.urls import path
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView, PasswordResetCompleteView


from . import views


urlpatterns = [
    path('', views.index, name='index'),
    path('search/', views.search, name='search'),
    path('no-permission', views.NoPermissionView.as_view(), name='no-permission'),
    path('detail/<int:pk>', views.ServiceDetailView.as_view(), name='service_detail'),
    path('cart', views.CartView.as_view(), name='cart'),
    path('shop', views.ShopListView.as_view(), name='shop'),
    path('redeem', login_required(views.RedeemView.as_view()), name='redeem'),
    path('redeem/confirm', login_required(views.RedeemConfirmView.as_view()),
         name='redeem_confirm'),
    path('redeem/done', login_required(views.RedeemDoneView.as_view()),
         name='redeem_done'),
    path('redeem/done/renew', login_required(views.RedeemRenewDoneView.as_view()),
         name='redeem_done_renew'),
    path('select', login_required(views.SelectAccView.as_view()), name='select_acc'),
#     path('checkout/<int:product_id>',
#          views.CheckOutView.as_view(), name='checkout'),
    path('addCart/<int:product_id>/<int:price>', views.addCart, name='addCart'),
    path('removeCart/<int:product_id>', views.removeCart, name='removeCart'),
    path('decrementCart/<int:product_id>/<int:unitPrice>',
         views.decrementCart, name='decrementCart'),
    path('login', views.LoginPageView.as_view(
        redirect_authenticated_user=True), name='login'),
    path('login/whatsapp', views.WhatsAppLoginView.as_view(), name='whatsapp_login'),
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
#     path('express-checkout/', views.MpWebhookUpdater, name='Mp_ExpressCheckout'),
    path('start_payment/',
         login_required(views.StartPayment), name='start_payment'),
    path('my_account/',
         login_required(views.MyAccountView.as_view()), name='my_account'),
#     path('test/', views.test, name='test'),
    path('privacy/', views.PrivacyView.as_view(), name='privacy'),
    path('tyc/', views.TermsAndConditionsView.as_view(), name='tyc'),
    path('webhook/mercadopago/', views.mp_webhook, name='mp_webhook'),
    path('api/send-whatsapp-verification/', views.send_whatsapp_verification, name='send_whatsapp_verification'),
    path('api/verify-whatsapp-code/', views.verify_whatsapp_code, name='verify_whatsapp_code'),
    path('api/send-whatsapp-login-code/', views.send_whatsapp_login_code, name='send_whatsapp_login_code'),
    path('api/whatsapp-login-verify/', views.whatsapp_login_verify_and_auth, name='whatsapp_login_verify_and_auth'),
    path('api/add-gift-days/', views.add_gift_days_to_account, name='add_gift_days_to_account'),

    # PayPal payment routes
    path('paypal/create-order/', views.paypal_create_order, name='paypal_create_order'),
    path('paypal/capture-order/', views.paypal_capture_order, name='paypal_capture_order'),
    path('paypal/success/', views.paypal_success, name='paypal_success'),
    path('paypal/cancel/', views.paypal_cancel, name='paypal_cancel'),
    path('webhook/paypal/', views.paypal_webhook, name='paypal_webhook'),
]

