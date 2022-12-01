#django
from django.urls import path
from django.contrib.auth.decorators import login_required


from . import views

app_name="adm"

urlpatterns = [
    #extension: /adm/
    path('',login_required(views.index),name='index'),
    path('no-permission',login_required(views.NoPermissionView.as_view()),name='no-permission'),
    path('settings',login_required(views.SettingsDetailView),name='settings'),
    path('settings/create',login_required(views.SettingsCreateView.as_view()),name='settings_create'),
    path('settings/update/<int:pk>',login_required(views.SettingsUpdateView.as_view()),name='settings_update'),
    path('profile/',login_required(views.ProfileView),name='profile'),
    path('profile/update/<int:pk>',login_required(views.UserUpdateView.as_view()),name='profile_update'),
    path('profile/update/details/<int:pk>',login_required(views.UserdetailUpdateView.as_view()),name='profile_update_details'),
    path('user/',login_required(views.UserView.as_view()),name='user'),
    path('user/update/<int:pk>',login_required(views.CustomerUpdateView.as_view()),name='user_update'),
    path('user/reference/<int:pk>',login_required(views.UserReferenceView),name='user_reference'),
    path('user/main/update/<int:pk>',login_required(views.MainUserUpdateView.as_view()),name='user_mainupdate'),
    path('services/',login_required(views.ServiceView.as_view()),name='services'),
    path('services/create/',login_required(views.ServiceCreateView.as_view()),name='services_create'),
    path('services/update/<int:pk>',login_required(views.ServiceUpdateView.as_view()),name='services_update'),
    path('services/delete/<int:pk>',login_required(views.ServiceDeleteView.as_view()),name='services_delete'),
    path('services/active/<str:status>/<int:pk>',login_required(views.ActiveInactiveService),name='active_inactive_service'),
    path('accounts',login_required(views.AccountsView),name='accounts'),
    path('accounts/expired',login_required(views.AccountsExpiredView),name='accounts_expired'),
    path('accounts/create',login_required(views.AccountsCreateView),name='accounts_create'),
    path('accounts/update/<int:pk>',login_required(views.AccountsUpdateView),name='accounts_update'),
    path('accounts/update/profile/<int:pk>',login_required(views.ProfileUpdateView.as_view()),name='accounts_update_profile'),
    path('accounts/active/<str:status>/<int:pk>',login_required(views.ActiveInactiveAccount),name='accounts_active'),
    path('bank',login_required(views.BankListView.as_view()),name='bank'),
    path('bank/create',login_required(views.bankCreateView.as_view()),name='bank_create'),
    path('bank/update/<int:pk>',login_required(views.BankUpdateView.as_view()),name='bank_update'),
    path('bank/delete/<int:pk>',login_required(views.BankDeleteView.as_view()),name='bank_delete'),
    path('paymentmethod/',login_required(views.PaymentMethodListView.as_view()),name='payment_method'),
    path('paymentmethod/create/',login_required(views.PaymentMethodCreateView.as_view()),name='payment_method_create'),
    path('paymentmethod/update/<int:pk>',login_required(views.PaymentMethodUpdateView.as_view()),name='payment_method_update'),
    path('paymentmethod/delete/<int:pk>',login_required(views.PaymentMethodDeleteView.as_view()),name='payment_method_delete'),
    path('status/',login_required(views.StatusListView.as_view()),name='status'),
    path('status/create/',login_required(views.StatusCreateView.as_view()),name='status_create'),
    path('status/update/<int:pk>',login_required(views.StatusUpdateView.as_view()),name='status_update'),
    path('status/delete/<int:pk>',login_required(views.StatusDeleteView.as_view()),name='status_delete'),
    path('supplier/',login_required(views.SupplierListView.as_view()),name='supplier'),
    path('supplier/create/',login_required(views.SupplierCreateView.as_view()),name='supplier_create'),
    path('supplier/update/<int:pk>',login_required(views.SupplierUpdateView.as_view()),name='supplier_update'),
    path('supplier/delete/<int:pk>',login_required(views.SupplierDeleteView.as_view()),name='supplier_delete'),
    path('sales',login_required(views.SalesView),name='sales'),
    path('sales/create/<int:pk>',login_required(views.SalesCreateView),name='sales_create'),
    path('sales/search',login_required(views.SalesSearchView),name='sales_search'),
    path('sales/search/detail',login_required(views.SalesSearchDetailView),name='sales_search_detail'),
    path('sales/update/status/<int:pk>/<int:customer>/<str:status>',login_required(views.SalesUpdateStatusView),name='sales_update_status'),
    path('sales/check/ticket',login_required(views.CheckTicket),name='check_ticket'),
    path('sales/renew/<int:pk>',login_required(views.RenewView),name='sales_renew'),
    path('sales/change/<int:pk>',login_required(views.SalesChangeView),name='sales_change'),
    path('sales/copy/<int:sale_id>',login_required(views.SalesCopyPass),name='sales_copy'),
    path('sales/old/<int:sale>',login_required(views.OldAccView),name='sales_old'),
    path('sales/FreeDays/<int:pk>,/<int:days>',login_required(views.SalesAddFreeDaysView),name='sales_add_free_days'),
    path('cupon/',login_required(views.CuponView.as_view()),name='cupon'),
    path('cupon/redeem',login_required(views.CuponRedeemView),name='cupon_redeem'),
    path('cupon/redeem/end',login_required(views.CuponRedeemEndView),name='cupon_redeem_end'),
    path('receivable/',login_required(views.ReceivableView.as_view()),name='receivable'),
    path('receivable/<int:sale_id>',login_required(views.ReceivableCopyPass),name='receivable_copy'),
    path('release/update/<int:pk>',login_required(views.ReleaseAccounts),name='release'),
    path('import',login_required(views.ImportView),name='import')
]