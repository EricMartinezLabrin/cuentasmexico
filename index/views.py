# Django
from django.shortcuts import render
from django.http import HttpResponse
from django.contrib.auth.views import LoginView, LogoutView, PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView, PasswordResetCompleteView
from django.contrib.auth.models import User, Group
from django.urls import reverse_lazy, reverse
from django.shortcuts import redirect
from django.views.generic import DetailView, CreateView, TemplateView, ListView, UpdateView
from django.views.generic.edit import FormView
from django.http import HttpResponseRedirect
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from index.models import IndexCart, IndexCartdetail
from index.payment_methods.MercagoPago import MercadoPago
from django.core.cache import cache

# local
from .forms import RegisterUserForm, RedeemForm
from adm.models import Level, UserDetail, Service, Sale, Account, Credits
from adm.functions.business import BusinessInfo
from .cart import CartProcessor, CartDb
from cupon.models import Shop, Cupon
from adm.functions.permissions import UserAccessMixin
from adm.functions.sales import Sales
from adm.functions.send_email import Email
from .models import IndexCart, IndexCartdetail

# Python
from datetime import timedelta
import json

# Index


def index(request):
    template_name = "index/index.html"

    return render(request, template_name, {
        'business': BusinessInfo.data(),
        'credits': BusinessInfo.credits(request),
        'services': Service.objects.filter(status=True),

    })


class CartView(TemplateView):
    template_name = "index/cart.html"

    def set_cart(self):
        cart = cache.get('cart')
        if cart is not None:
            return cart
        if not self.request.session.get('cart_number'):
            return None
        cart = CartDb.create_full_cart(self).id
        mp = MercadoPago(self.request)
        result = mp.Mp_ExpressCheckout(cart)
        # Guarda el valor en caché durante 24 horas
        cache.set('cart', result, timeout=60*60*24)
        return result

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["business"] = BusinessInfo.data()
        context["credits"] = BusinessInfo.credits(self.request)
        context['services'] = Service.objects.filter(status=True)
        context["init_point"] = self.set_cart()
        return context


# class CheckOutView(TemplateView):
#     template_name = "index/checkout.html"

#     def get_context_data(self, **kwargs):
#         preference_id = None
#         cart_data = None

#         if not self.request.user == "AnonymousUser":
#             cart_detail = CartDb.CartAll(self, self.request)
#             if cart_detail:
#                 cart = IndexCart.objects.get(pk=cart_detail.cart.id)
#                 cart_data = IndexCartdetail.objects.filter(cart=cart)
#                 cart_id = cart_detail.cart.id
#                 preference_id = MercadoPago.Mp_ExpressCheckout(
#                     self.request, cart_id)

#         procesor = CartProcessor(self.request)
#         procesor.clear()

#         context = super().get_context_data(**kwargs)
#         context["business"] = BusinessInfo.data()
#         context["credits"] = BusinessInfo.credits(self.request)
#         context['services'] = Service.objects.filter(status=True)
#         return context


class ServiceDetailView(DetailView):
    model = Service
    template_name = 'index/service_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["count"] = BusinessInfo.count_sales(self.kwargs['pk'])
        context["business"] = BusinessInfo.data()
        context["credits"] = BusinessInfo.credits(self.request)
        context['services'] = Service.objects.filter(status=True)
        return context


class ShopListView(ListView):
    model = Shop
    template_name = "index/shop.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["business"] = BusinessInfo.data()
        context["credits"] = BusinessInfo.credits(self.request)
        context['services'] = Service.objects.filter(status=True)
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


class RedeemView(UserAccessMixin, FormView):
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
            active_acc = Sale.objects.filter(customer=user, status=True)
            return active_acc

    def get_error(self):
        error = None
        if self.get_code():
            if self.get_code().customer:
                error = "El código ya fue utilizado, si no lo canjeó usted, porfavor, contacte a su vendedor y pidale uno nuevo."

        return error

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["business"] = BusinessInfo.data()
        context["credits"] = BusinessInfo.credits(self.request)
        context['services'] = Service.objects.filter(status=True)
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
        context["business"] = BusinessInfo.data()
        context["credits"] = BusinessInfo.credits(self.request)
        context['services'] = Service.objects.filter(status=True)
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
                account = Service.objects.get(
                    pk=self.request.GET.get('service'))
            except Service.DoesNotExist:
                account = Account.objects.get(
                    pk=self.request.GET.get('service'))
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
        context["business"] = BusinessInfo.data()
        context["credits"] = BusinessInfo.credits(self.request)
        context['services'] = Service.objects.filter(status=True)
        return context


class RedeemRenewDoneView(TemplateView):
    template_name = "index/redeem_done.html"

    def complete_redeem(self):
        code = self.request.GET.get('name')
        service_id = self.request.GET.get('service')
        service = Account.objects.get(pk=service_id)
        customer = self.request.user.id

        renew = Sales.redeem_renew(self.request, service, code, customer)

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
        context["business"] = BusinessInfo.data()
        context["credits"] = BusinessInfo.credits(self.request)
        context['services'] = Service.objects.filter(status=True)
        context["account"] = self.complete_redeem()
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
                account = Sales.search_better_acc(service_id, end_date, code)
            else:
                account = (
                    False, "Error. El código ya fue utilizado, si no lo canjeó usted contacte a su vendedor y pidale uno nuevo.")

            if account[0] == True:
                Sales.redeem(self.request, account[1], code, customer)
            return account
        except Cupon.DoesNotExist:
            return False, "El código no existe, porfavor contacte a su vendedor y pidale uno nuevo."

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
        context["business"] = BusinessInfo.data()
        context["credits"] = BusinessInfo.credits(self.request)
        context['services'] = Service.objects.filter(status=True)
        context["account"] = self.complete_redeem()
        context["code"] = self.get_code()
        return context


# Cart
def addCart(request, product_id, price):
    cart = CartProcessor(request)
    service = Service.objects.get(pk=product_id)
    if request.method == 'POST':
        quantity = int(request.POST.get('quantity'))
        profiles = int(request.POST.get('profiles'))
        price_unit = int(request.POST.get('price'))
        cart.add(product=service, quantity=quantity,
                 profiles=profiles, price=price_unit)
        return HttpResponseRedirect(reverse("cart"))
    cart.add(service, 1, 1, price)
    return HttpResponseRedirect(reverse("cart"))


def removeCart(request, product_id):
    cart = CartProcessor(request)
    service = Service.objects.get(pk=product_id)
    cart.remove(service)
    return HttpResponseRedirect(reverse("cart"))


def decrementCart(request, product_id, unitPrice):
    cart = CartProcessor(request)
    service = Service.objects.get(pk=product_id)
    cart.decrement(service, unitPrice)
    return HttpResponseRedirect(reverse("cart"))


# Users Actions
class LoginPageView(LoginView):
    """
    Login a user and redirect to a verifier of permission on RedirectOnLoginView
    """
    template_name = "index/login.html"

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        response.xframe_options_exempt = True
        if 'X-Frame-Options' in response:
            del response['X-Frame-Options']
        return response

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        response.xframe_options_exempt = True
        if 'X-Frame-Options' in response:
            del response['X-Frame-Options']
        return response
        return response

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if 'X-Frame-Options' in response.headers:
            del response.headers['X-Frame-Options']
        return response
    model = User

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["business"] = BusinessInfo.data()
        context["credits"] = BusinessInfo.credits(self.request)
        context['services'] = Service.objects.filter(status=True)
        return context


class LogoutPageView(LogoutView):
    """
    Log Out User
    """


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
        context["business"] = BusinessInfo.data()
        context["credits"] = BusinessInfo.credits(self.request)
        context['services'] = Service.objects.filter(status=True)
        return context


class ChangePasswordView(PasswordResetView):
    template_name = 'index/registration/change_password.html'
    email_template_name = 'index/registration/password_reset_email.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["business"] = BusinessInfo.data()
        context["credits"] = BusinessInfo.credits(self.request)
        context['services'] = Service.objects.filter(status=True)
        return context


class EmailUpdateView(UpdateView):
    model = User
    template_name = "index/registration/change_email.html"
    fields = ['email']
    success_url = reverse_lazy('my_account')


class PassResetView(PasswordResetView):
    template_name = 'index/registration/password_reset_form.html'
    email_template_name = 'index/registration/password_reset_email.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["business"] = BusinessInfo.data()
        context["credits"] = BusinessInfo.credits(self.request)
        context['services'] = Service.objects.filter(status=True)
        return context


class PassResetDoneView(PasswordResetDoneView):
    template_name = 'index/registration/password_reset_done.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["business"] = BusinessInfo.data()
        context["credits"] = BusinessInfo.credits(self.request)
        context['services'] = Service.objects.filter(status=True)
        return context


class PassResetConfirmView(PasswordResetConfirmView):
    template_name = 'index/registration/password_reset_confirm.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["business"] = BusinessInfo.data()
        context["credits"] = BusinessInfo.credits(self.request)
        context['services'] = Service.objects.filter(status=True)
        return context


class PassResetPasswordCompleteView(PasswordResetCompleteView):
    """
    Show message if password has correctly changed
    """
    template_name = 'index/registration/password_reset_complete.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["business"] = BusinessInfo.data()
        context["credits"] = BusinessInfo.credits(self.request)
        context['services'] = Service.objects.filter(status=True)
        return context


def RedirectOnLogin(request):
    """
    Verify permission and details of User and redirect to Main Page or Admin Page
    """
    admin_list = ['superadmin', 'admin', 'supervisor', 'salesman']
    # Verify Details
    try:
        user = request.user.id
        user_details = UserDetail.objects.get(user_id=user)
        try:
            user_level = user_details.level.name
        except AttributeError:
            customer_level = Level.objects.get(name='Cliente')
            user_details.level = customer_level
            user_details.save()
            user_level = user_details.level.name
    except UserDetail.DoesNotExist:
        customer_level = Level.objects.get(name='Cliente')
        user_details = UserDetail.objects.create(
            phone_number=0, lada=0, country="", business_id=1, user_id=user, level=customer_level)
        user_level = user_details.level.name

    if not user_level in admin_list:
        template_name = 'index'
    else:
        template_name = 'adm:sales'

    return redirect(reverse(template_name))


class NoPermissionView(TemplateView):
    """
    Page where are redirected users with out permissions
    """
    template_name = "index/no_permission.html"

    def not_allowed(self):
        staff = self.request.user.is_staff
        print(staff)
        if not staff:
            return redirect('index')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["business"] = BusinessInfo.data()
        context["credits"] = BusinessInfo.credits(self.request)
        context['services'] = Service.objects.filter(status=True)
        return context


def SendEmail(request):
    template_name = "index/email.html"
    acc = Sale.objects.filter(pk__lte=3)

    if request.method == 'POST':
        Email.email_passwords(request, 'contacto@cuentasmexico.mx', acc)

    return render(request, template_name, {})


class NoCreditsView(TemplateView):
    template_name = "index/no_credits.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["business"] = BusinessInfo.data()
        context["credits"] = BusinessInfo.credits(self.request)
        context['services'] = Service.objects.filter(status=True)
        return context


def DistributorSale(request):
    customer = request.user
    cart = request.session.get('cart_number')
    total = request.session.get('cart_total')
    credits_availables = BusinessInfo.credits(request)
    no_credits = "index/no_credits.html"
    template_name = "index/sale.html"
    # check if enoght credits
    if credits_availables < total:
        return redirect(request, no_credits)

    cartEnd = []

    for key, values in cart.items():
        for i in range(values['profiles']):
            expiration_date = timezone.now() + timedelta(days=30 *
                                                         values['quantity'])
            new_acc = Sales.search_better_acc(
                values['product_id'], expiration_date, None)
            quantity = values['quantity']
            service_name = values['name']
            price = (int(values['unitPrice'])*int(values['quantity']))*-1

            print(new_acc)
            if new_acc == None:
                return HttpResponse('Tenemos problemas para completar tu orden, porfavor contactate con atencion al cliente.')

            elif new_acc[0] == False:
                return HttpResponse(new_acc[1])
            else:
                sale = Sales.web_sale(
                    request, new_acc[1], values['unitPrice'], values['quantity'])
                sale_id = sale['id']
                Sales.credits_modify(
                    customer, price, f'Orden {sale_id}: {quantity} meses de {service_name}.')
                cartEnd.append(sale)

    cartprocesor = CartProcessor(request)
    cartprocesor.clear()
    print(cartEnd)

    return render(request, template_name, {
        "account": cartEnd,
        'business': BusinessInfo.data(),
        'credits': BusinessInfo.credits(request),
        'services': Service.objects.filter(status=True),

    })


# @csrf_exempt
# def MpWebhookUpdater(request):
#     if request.method == 'POST':
#         body = request.body.decode('utf-8')
#         data = json.loads(body)
#         if data['type'] == 'payment':
#             payment_data = MercadoPago.search_payments(data['data']['id'])
#             cart_updated = MercadoPago.webhook_updater(payment_data)
#             # Make Sale.
#             cart_updated_obj = IndexCart.objects.get(
#                 pk=payment_data['external_reference'])
#             cart_data = IndexCartdetail.objects.filter(cart=cart_updated_obj)
#             for cart_detail in cart_data:
#                 service_id = cart_detail.service.id
#                 expiration = timezone.now() + timedelta(days=cart_detail.long*30)
#                 for i in range(cart_detail.quantity):
#                     service = Sales.search_better_acc(
#                         service_id=service_id, exp=expiration)[1]
#                     Credits.objects.create(customer=User.objects.get(
#                         username='3338749736'), credits=100, detail=service)
#                     sale = Sales.sale_ok(customer=cart_updated_obj.customer, webhook_provider="MercadoPago", payment_type=cart_updated_obj.payment_type_id,
#                                          service_obj=service, expiration_date=expiration, unit_price=cart_detail.price, payment_id=cart_updated_obj.payment_id)
#                     Credits.objects.create(customer=User.objects.get(
#                         username='3338749736'), credits=100, detail=sale)
#         return HttpResponse(200)
#     else:
#         return HttpResponse(404)


@csrf_exempt
def mp_webhook(request):
    """
    Webhook para recibir notificaciones de MercadoPago.
    Procesa pagos aprobados y entrega las cuentas al cliente.
    """
    import logging
    import hmac
    import hashlib
    import os

    logger = logging.getLogger(__name__)

    if request.method != 'POST':
        return HttpResponse(status=405)

    # Verificar firma del webhook
    webhook_secret = os.environ.get('MP_WEBHOOK_SECRET')
    if webhook_secret:
        x_signature = request.headers.get('x-signature', '')
        x_request_id = request.headers.get('x-request-id', '')

        # Obtener data.id de query params (MP lo envía así)
        data_id = request.GET.get('data.id', '')

        # Parsear x-signature (formato: ts=xxx,v1=xxx)
        ts = ''
        received_hash = ''
        for part in x_signature.split(','):
            if part.startswith('ts='):
                ts = part[3:]
            elif part.startswith('v1='):
                received_hash = part[3:]

        # Construir el manifest para verificar
        # Formato: id:{data.id};request-id:{x-request-id};ts:{ts};
        manifest = f"id:{data_id};request-id:{x_request_id};ts:{ts};"

        # Calcular HMAC-SHA256
        calculated_hash = hmac.new(
            webhook_secret.encode(),
            manifest.encode(),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(calculated_hash, received_hash):
            logger.warning(f"Firma de webhook inválida. Recibido: {received_hash}, Calculado: {calculated_hash}")
            # En desarrollo, solo loguear pero continuar
            if not os.environ.get('DEBUG', 'False').lower() == 'true':
                return HttpResponse(status=401)

    try:
        body = request.body.decode('utf-8')
        data = json.loads(body)

        logger.info(f"MP Webhook recibido: {data}")

        # MercadoPago envía diferentes tipos de notificaciones
        notification_type = data.get('type') or data.get('action')

        if notification_type == 'payment':
            payment_id = data.get('data', {}).get('id')
            if not payment_id:
                logger.warning("Webhook sin payment_id")
                return HttpResponse(status=400)

            # Buscar información del pago en MercadoPago
            mp = MercadoPago(request)
            payment_data = mp.search_payments(payment_id)

            if not payment_data:
                logger.error(f"No se pudo obtener info del pago {payment_id}")
                return HttpResponse(status=500)

            # Solo procesar pagos aprobados
            if payment_data.get('status') != 'approved':
                logger.info(f"Pago {payment_id} no aprobado: {payment_data.get('status')}")
                return HttpResponse(status=200)

            # Obtener el carrito usando external_reference
            cart_id = payment_data.get('external_reference')
            if not cart_id:
                logger.error("Pago sin external_reference")
                return HttpResponse(status=400)

            try:
                cart = IndexCart.objects.get(pk=cart_id)
            except IndexCart.DoesNotExist:
                logger.error(f"Carrito {cart_id} no encontrado")
                return HttpResponse(status=404)

            # Verificar si ya fue procesado (evitar duplicados)
            if cart.status_detail == 'approved':
                logger.info(f"Carrito {cart_id} ya fue procesado")
                return HttpResponse(status=200)

            # Actualizar carrito con datos del pago
            cart.payment_id = payment_data.get('id')
            cart.date_approved = timezone.now()
            cart.payment_type_id = payment_data.get('payment_type_id')
            cart.status_detail = payment_data.get('status')
            cart.transaction_amount = payment_data.get('transaction_amount')
            cart.save()

            # Obtener items del carrito
            cart_details = IndexCartdetail.objects.filter(cart=cart)
            customer = cart.customer
            sales_created = []

            for cart_detail in cart_details:
                service_id = cart_detail.service.id
                months = cart_detail.long  # duración en meses
                profiles = cart_detail.quantity  # cantidad de perfiles
                unit_price = cart_detail.price

                # Calcular fecha de expiración
                expiration = timezone.now() + timedelta(days=months * 30)

                # Crear una venta por cada perfil solicitado
                for i in range(profiles):
                    # Buscar cuenta disponible
                    result = Sales.search_better_acc(service_id=service_id, exp=expiration)

                    # Validar que result no sea None
                    if result is None:
                        logger.warning(f"search_better_acc retornó None para servicio {service_id}")
                        continue

                    if result[0]:  # Si encontró cuenta disponible
                        account = result[1]
                        # Crear la venta
                        sale_result = Sales.sale_ok(
                            customer=customer,
                            webhook_provider="MercadoPago",
                            payment_type=payment_data.get('payment_type_id', 'unknown'),
                            payment_id=str(payment_id),
                            service_obj=account,
                            expiration_date=expiration,
                            unit_price=unit_price
                        )
                        if sale_result and sale_result[0]:
                            sales_created.append(sale_result[1])
                            logger.info(f"Venta creada: {sale_result[1].id} para {customer.username}")
                    else:
                        logger.warning(f"No hay cuentas disponibles para servicio {service_id}: {result[1]}")

            logger.info(f"Webhook procesado: {len(sales_created)} ventas creadas para carrito {cart_id}")
            return HttpResponse(status=200)

        # Para otros tipos de notificación, solo confirmar recepción
        return HttpResponse(status=200)

    except json.JSONDecodeError:
        logger.error("Error decodificando JSON del webhook")
        return HttpResponse(status=400)
    except Exception as e:
        logger.exception(f"Error procesando webhook: {str(e)}")
        return HttpResponse(status=500)


def StartPayment(request):
    cart = CartProcessor(request)
    cart.clear()
    cache.set('cart', "0", timeout=0)
    init_point = request.GET.get('initpoint')
    return redirect(init_point)


class MyAccountView(TemplateView):
    template_name = "index/my_account.html"

    def find_renovables(self, account):
        renovable = []
        accounts = []
        for data in set(account):
            if data.status == 0 or data.account in accounts:
                continue
            if not data.account.customer:
                if data.account.renovable:
                    renovable.append(data)
                    accounts.append(data.account)
        return renovable

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["business"] = BusinessInfo.data()
        context["credits"] = BusinessInfo.credits(self.request)
        context['services'] = Service.objects.filter(status=True)
        context['active'] = Sales.customer_sales_active(self.request.user)
        context['inactive'] = self.find_renovables(Sales.customer_sales_inactive(
            self.request.user))
        context['now'] = timezone.now()
        return context


# def test(request):
#     cart_updated = IndexCart.objects.get(pk=177)
#     cart_data = IndexCartdetail.objects.filter(cart=cart_updated)
#     for cart_detail in cart_data:
#         service_id = cart_detail.service.id
#         expiration = timezone.now() + timedelta(days=cart_detail.long*30)
#         for i in range(cart_detail.quantity):
#             service = Sales.search_better_acc(
#                 service_id=service_id, exp=expiration)[1]
#             sale = Sales.sale_ok(customer=cart_updated.customer, webhook_provider="MercadoPago",
#                                  payment_type=cart_updated.payment_type_id, service_obj=service, expiration_date=expiration, unit_price=cart_detail.price, payment_id=cart_updated.payment_id)

#     return HttpResponse(sale)


class PrivacyView(TemplateView):
    """
    Política de privacidad
    """
    template_name = "index/privacy.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['now'] = timezone.now()
        return context


class TermsAndConditionsView(TemplateView):
    """
    Términos y condiciones
    """
    template_name = "index/tyc.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['now'] = timezone.now()
        return context


def search(request):
    """
    Búsqueda de productos/servicios
    """
    template_name = "index/search.html"
    query = request.GET.get('q', '')
    results = []

    if query:
        results = Service.objects.filter(
            description__icontains=query,
            status=True
        )

    return render(request, template_name, {
        'business': BusinessInfo.data(),
        'credits': BusinessInfo.credits(request),
        'services': Service.objects.filter(status=True),
        'query': query,
        'results': results,
    })
