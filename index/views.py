# Django
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.views import LoginView, LogoutView, PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView, PasswordResetCompleteView
from django.contrib.auth.models import User, Group
from django.contrib.auth.decorators import login_required
from django.urls import reverse_lazy, reverse
from django.shortcuts import redirect
from django.views.generic import DetailView, CreateView, TemplateView, ListView, UpdateView
from django.views.generic.edit import FormView
from django.http import HttpResponseRedirect
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db import transaction
from index.models import IndexCart, IndexCartdetail
from index.payment_methods.MercagoPago import MercadoPago
from index.payment_methods.PayPal import PayPal
from index.payment_methods.Stripe import StripePayment
from index.payment_methods.utils import get_masked_product_name, get_masked_description
from django.core.cache import cache
import stripe

# Configuracion de metodos de pago habilitados
# Para habilitar MercadoPago, cambiar a True
MERCADOPAGO_ENABLED = False
PAYPAL_ENABLED = True
STRIPE_ENABLED = False

# local
from .forms import RegisterUserForm, RedeemForm, WhatsAppLoginForm
from adm.models import Level, UserDetail, Service, Sale, Account, Credits, PaymentMethod, AccountChangeHistory
from adm.functions.business import BusinessInfo
from .cart import CartProcessor, CartDb
from cupon.models import Shop
from cupon.services import (
    CouponRedeemError,
    get_coupon_by_name_or_raise,
    validate_coupon_for_customer,
)
from adm.functions.permissions import UserAccessMixin
from adm.functions.sales import Sales
from adm.functions.send_email import Email
from .models import IndexCart, IndexCartdetail

# Python
from datetime import timedelta
import json
from urllib.request import urlopen
from urllib.parse import quote, urlparse, parse_qs
from urllib.error import URLError, HTTPError

# Afiliados
from .utils_affiliates import procesar_venta_afiliado_desde_carrito

# Index
POST_LOGIN_REDIRECT_SESSION_KEY = 'post_login_redirect_to'
WHATSAPP_LOGIN_NEXT_CACHE_SUFFIX = ':next'


def _sanitize_post_login_redirect(request, target_url):
    if not target_url:
        return None

    target_url = str(target_url).strip()
    if not target_url:
        return None

    # Evita redirecciones abiertas y valida que sea interna/permitida.
    if not url_has_allowed_host_and_scheme(
        url=target_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return None

    blocked_paths = {
        reverse('login'),
        reverse('whatsapp_login'),
        reverse('logout'),
    }
    if any(target_url.startswith(path) for path in blocked_paths):
        return None

    return target_url


def _store_post_login_redirect(request, target_url):
    safe_target = _sanitize_post_login_redirect(request, target_url)
    if safe_target:
        request.session[POST_LOGIN_REDIRECT_SESSION_KEY] = safe_target
    return safe_target


def _get_post_login_redirect(request, pop=False):
    if pop:
        target_url = request.session.pop(POST_LOGIN_REDIRECT_SESSION_KEY, None)
    else:
        target_url = request.session.get(POST_LOGIN_REDIRECT_SESSION_KEY)
    return _sanitize_post_login_redirect(request, target_url)


def _get_next_from_referer(request):
    referer = str(request.META.get("HTTP_REFERER") or "").strip()
    if not referer:
        return None
    try:
        parsed = urlparse(referer)
        values = parse_qs(parsed.query or "")
        raw_next = (values.get("next") or [None])[0]
    except Exception:
        return None
    return _sanitize_post_login_redirect(request, raw_next)


def index(request):
    from adm.models import IndexCarouselImage, IndexPromoImage
    from adm.functions.promociones import PromocionManager
    template_name = "index/index.html"

    # Obtener imágenes activas
    carousel_images = IndexCarouselImage.objects.filter(active=True).order_by('order')
    promo_images = IndexPromoImage.objects.filter(active=True).order_by('position')

    # Separar promociones por posición
    promo_left = promo_images.filter(position='left').first()
    promo_right = promo_images.filter(position='right').first()

    # Obtener servicios y aplicar promociones
    servicios = Service.objects.filter(status=True)
    servicios_con_promocion = PromocionManager.aplicar_promociones_a_servicios(servicios)

    # Obtener banners de promociones
    promociones_banner = PromocionManager.obtener_promociones_banner()

    return render(request, template_name, {
        'business': BusinessInfo.data(),
        'credits': BusinessInfo.credits(request),
        'services': Service.objects.filter(status=True),
        'servicios_con_promocion': servicios_con_promocion,
        'carousel_images': carousel_images,
        'promo_left': promo_left,
        'promo_right': promo_right,
        'promociones_banner': promociones_banner,
    })


class CartView(TemplateView):
    template_name = "index/cart.html"

    def set_cart_mercadopago(self, cart_db):
        """Configura el pago con MercadoPago (deshabilitado por defecto)"""
        if not MERCADOPAGO_ENABLED:
            return None

        cached = cache.get('cart_mp')
        if cached is not None:
            return cached

        mp = MercadoPago(self.request)
        result = mp.Mp_ExpressCheckout(cart_db.id)
        if result:
            cache.set('cart_mp', result, timeout=60*60*24)
        return result

    def set_cart_paypal(self, cart_db):
        """Prepara los datos para PayPal"""
        if not PAYPAL_ENABLED:
            return None

        # Preparar items del carrito para PayPal
        items, subtotal = PayPal.get_cart_items_for_paypal(self.request)
        if not items:
            return None

        return {
            'cart_id': cart_db.id,
            'items': items,
            'subtotal': subtotal,
            'ready': True
        }

    def set_cart_stripe(self, cart_db):
        """Prepara los datos para Stripe"""
        if not STRIPE_ENABLED:
            return None

        # Preparar items del carrito para Stripe
        items, subtotal = StripePayment.get_cart_items_for_stripe(self.request)
        if not items:
            return None

        return {
            'cart_id': cart_db.id,
            'items': items,
            'subtotal': subtotal,
            'ready': True
        }

    def get_context_data(self, **kwargs):
        import os
        from index.utils_affiliates import calcular_descuento_carrito

        context = super().get_context_data(**kwargs)
        context["business"] = BusinessInfo.data()
        context["credits"] = BusinessInfo.credits(self.request)
        context['services'] = Service.objects.filter(status=True)

        # Metodos de pago habilitados
        context['mercadopago_enabled'] = MERCADOPAGO_ENABLED
        context['paypal_enabled'] = PAYPAL_ENABLED
        context['stripe_enabled'] = STRIPE_ENABLED

        # PayPal Client ID para el SDK de JavaScript
        context['paypal_client_id'] = os.environ.get('PAYPAL_CLIENT_ID', 'sb')

        # Stripe Publishable Key para el SDK de JavaScript
        context['stripe_publishable_key'] = os.environ.get('STRIPE_PUBLISHABLE_KEY', '')

        # Inicializar valores de pago
        context["init_point"] = None  # MercadoPago
        context["paypal_data"] = None  # PayPal
        context["stripe_data"] = None  # Stripe

        # Calcular descuento efectivo (mayor entre promocion y afiliado)
        descuento_info = calcular_descuento_carrito(self.request)
        context['descuento_info'] = descuento_info

        # Guardar total con descuento en sesion para usarlo en pagos
        if descuento_info['tiene_descuento']:
            self.request.session['cart_total_con_descuento'] = descuento_info['total_final']
            self.request.session['descuento_aplicado'] = descuento_info['descuento_total']
            self.request.session['descuento_tipo'] = descuento_info['tipo_descuento']
            self.request.session['descuento_nombre'] = descuento_info['nombre_descuento']
        else:
            self.request.session['cart_total_con_descuento'] = self.request.session.get('cart_total', 0)
            self.request.session['descuento_aplicado'] = 0
            self.request.session['descuento_tipo'] = None
            self.request.session['descuento_nombre'] = None

        # Solo procesar si hay carrito y usuario autenticado
        if not self.request.session.get('cart_number'):
            return context
        if not self.request.user.is_authenticated:
            return context

        # Crear carrito en BD
        cart_db = CartDb.create_full_cart(self)
        if cart_db is None:
            return context

        # Configurar metodos de pago disponibles
        if MERCADOPAGO_ENABLED:
            context["init_point"] = self.set_cart_mercadopago(cart_db)

        if PAYPAL_ENABLED:
            context["paypal_data"] = self.set_cart_paypal(cart_db)

        if STRIPE_ENABLED:
            context["stripe_data"] = self.set_cart_stripe(cart_db)

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
        from index.utils_affiliates import calcular_descuento_efectivo
        
        context = super().get_context_data(**kwargs)
        context["count"] = BusinessInfo.count_sales(self.kwargs['pk'])
        context["business"] = BusinessInfo.data()
        context["credits"] = BusinessInfo.credits(self.request)
        context['services'] = Service.objects.filter(status=True)
        
        # Calcular descuento efectivo (promocion vs afiliado)
        servicio = self.get_object()
        descuento_info = calcular_descuento_efectivo(self.request, servicio)
        context['descuento_efectivo'] = descuento_info
        
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

    def has_permission(self):
        """
        Compatibilidad para acceso de clientes:
        - Grupo Django: "Cliente"
        - Nivel en UserDetail: "Cliente"
        """
        user = self.request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        if user.groups.filter(name__iexact='Cliente').exists():
            return True
        try:
            detail = UserDetail.objects.select_related('level').get(user=user)
            if detail.level and str(detail.level.name or '').strip().lower() == 'cliente':
                return True
        except UserDetail.DoesNotExist:
            pass
        return False

    def get_code(self):
        if self.request.GET.get('name'):
            code = self.request.GET.get('name')
            try:
                return get_coupon_by_name_or_raise(code)
            except CouponRedeemError:
                return None
        else:
            code = None

    def get_active_acc(self):
        if self.request.user:
            user = self.request.user
            active_acc = Sale.objects.filter(customer=user, status=True)
            code = self.get_code()
            if code:
                excluded_ids = code.excluded_services.values_list('id', flat=True)
                active_acc = active_acc.exclude(account__account_name_id__in=excluded_ids)
            return active_acc

    def get_error(self):
        code = self.get_code()
        if not code:
            return None
        try:
            validate_coupon_for_customer(code, self.request.user)
        except CouponRedeemError as exc:
            return str(exc)
        return None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["business"] = BusinessInfo.data()
        context["credits"] = BusinessInfo.credits(self.request)
        context['services'] = Service.objects.filter(status=True)
        context["error"] = self.get_error()
        context["code"] = self.get_code()
        context["customer_data"] = self.get_active_acc()
        return context


@login_required
def redeem_code_shortcut(request, code):
    normalized = (code or '').strip()
    if not normalized:
        return redirect('redeem')
    return redirect(f"{reverse('redeem')}?name={quote(normalized)}")


class SelectAccView(TemplateView):
    template_name = "index/select_acc.html"
    code = None
    error = None

    def get_code(self):
        if self.request.GET.get('name'):
            code = self.request.GET.get('name')
            try:
                return get_coupon_by_name_or_raise(code)
            except CouponRedeemError:
                return None

    def get_availables(self):
        available = Service.objects.filter(status=True)
        code = self.get_code()
        if code:
            excluded_ids = code.excluded_services.values_list('id', flat=True)
            available = available.exclude(id__in=excluded_ids)
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
            try:
                return get_coupon_by_name_or_raise(code)
            except CouponRedeemError:
                return None

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
        code = self.get_code()
        if not code:
            return "El código no existe."
        account = self.account()
        service = account.account_name if isinstance(account, Account) else account
        try:
            validate_coupon_for_customer(code, self.request.user, service=service)
        except CouponRedeemError as exc:
            return f"Error. {str(exc)}"
        return None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["error"] = self.get_error()
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

        try:
            renew = Sales.redeem_renew(self.request, service, code, customer)
            return renew
        except (Account.DoesNotExist, CouponRedeemError) as exc:
            return False, str(exc)

    def get_code(self):
        if self.request.GET.get('name'):
            code = self.request.GET.get('name')
            try:
                return get_coupon_by_name_or_raise(code)
            except CouponRedeemError:
                return None

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
            cupon = get_coupon_by_name_or_raise(code)
            service = Service.objects.get(pk=service_id)
            validate_coupon_for_customer(cupon, self.request.user, service=service)
            end_date = cupon.get_expiration_date(timezone.now())
            customer = self.request.user.id

            account = Sales.search_better_acc(service_id, end_date, code)

            if account[0] == True:
                Sales.redeem(self.request, account[1], code, customer)
            return account
        except CouponRedeemError as exc:
            return False, str(exc)

    def get_code(self):
        if self.request.GET.get('name'):
            code = self.request.GET.get('name')
            try:
                return get_coupon_by_name_or_raise(code)
            except CouponRedeemError:
                return None

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
        _store_post_login_redirect(request, request.GET.get(self.redirect_field_name))
        response = super().get(request, *args, **kwargs)
        response.xframe_options_exempt = True
        if 'X-Frame-Options' in response:
            del response['X-Frame-Options']
        return response

    def post(self, request, *args, **kwargs):
        _store_post_login_redirect(request, request.POST.get(self.redirect_field_name) or request.GET.get(self.redirect_field_name))
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


class WhatsAppLoginView(TemplateView):
    """
    Login a user via WhatsApp verification
    """
    template_name = "index/whatsapp_login.html"

    def get(self, request, *args, **kwargs):
        _store_post_login_redirect(request, request.GET.get('next'))
        response = super().get(request, *args, **kwargs)
        response.xframe_options_exempt = True
        if 'X-Frame-Options' in response:
            del response['X-Frame-Options']
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["business"] = BusinessInfo.data()
        context["credits"] = BusinessInfo.credits(self.request)
        context['services'] = Service.objects.filter(status=True)
        context['form'] = WhatsAppLoginForm()
        context['post_login_redirect'] = (
            _sanitize_post_login_redirect(self.request, self.request.GET.get('next'))
            or _get_post_login_redirect(self.request)
            or ''
        )
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

    def form_valid(self, form):
        from .whatsapp_verification import WhatsAppVerification
        from index.phone_utils import PhoneNumberHandler
        from adm.models import Business

        # Obtener datos del formulario
        phone_number = form.cleaned_data.get('phone_number')
        country = form.cleaned_data.get('country')

        # Normalizar número según el país
        normalized = PhoneNumberHandler.normalize_phone_by_country(phone_number, country)
        db_number = normalized['db_number']

        # Verificar que el número no esté ya registrado (doble verificación usando db_number)
        existing_user = UserDetail.objects.filter(
            phone_number=db_number,
            country=country
        ).first()

        if existing_user:
            form.add_error(None, 'Este número de teléfono ya está registrado')
            return self.form_invalid(form)

        # Verificar que el teléfono haya sido verificado (usando db_number)
        if not WhatsAppVerification.is_verified(db_number, country):
            form.add_error(None, 'Debes verificar tu número de WhatsApp antes de registrarte')
            return self.form_invalid(form)

        # Crear el usuario
        user = form.save(commit=False)
        user.is_active = True
        user.save()

        # Asignar el usuario creado a self.object para que get_success_url() funcione
        self.object = user

        # Intentar agregar al grupo de clientes si existe
        try:
            customer_group = Group.objects.get(name='Cliente')
            user.groups.add(customer_group)
        except Group.DoesNotExist:
            pass

        # Obtener la lada del país
        lada = WhatsAppVerification.get_lada_from_country(country)

        # Crear UserDetail con la información de WhatsApp (guardar db_number en phone_number)
        try:
            business = Business.objects.get(id=1)
            UserDetail.objects.create(
                user=user,
                phone_number=db_number,
                lada=int(lada) if lada else 0,
                country=country,
                business=business
            )
        except Business.DoesNotExist:
            # Si no existe el business, eliminar el usuario creado
            user.delete()
            form.add_error(None, 'Error en la configuración del sistema')
            return self.form_invalid(form)

        return HttpResponseRedirect(self.get_success_url())


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
    pending_redirect = (
        _sanitize_post_login_redirect(request, request.GET.get('next'))
        or _get_post_login_redirect(request, pop=True)
    )
    if pending_redirect:
        return redirect(pending_redirect)

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
        Email.email_passwords(request, 'contacto@cuentasmexico.com', acc)

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
            logger.warning(f"Manifest usado: {manifest}")
            logger.warning(f"data.id: {data_id}, x-request-id: {x_request_id}, ts: {ts}")
            # TEMPORALMENTE: continuar aunque falle la firma para debug
            # TODO: Descomentar cuando se corrija la verificación de firma
            # if not os.environ.get('DEBUG', 'False').lower() == 'true':
            #     return HttpResponse(status=401)

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
            items_without_stock = []

            for cart_detail in cart_details:
                service_id = cart_detail.service.id
                service_name = cart_detail.service.description
                months = cart_detail.long  # duración en meses
                profiles = cart_detail.quantity  # cantidad de perfiles
                unit_price = cart_detail.price

                # Calcular fecha de expiración
                expiration = timezone.now() + timedelta(days=months * 30)

                logger.info(f"Procesando servicio {service_name} (ID: {service_id}): {profiles} perfiles x {months} meses")

                # Crear una venta por cada perfil solicitado
                profiles_without_stock = 0
                for i in range(profiles):
                    logger.info(f"  Buscando cuenta {i+1}/{profiles} para {service_name}...")

                    # Buscar la mejor cuenta disponible usando la lógica optimizada
                    try:
                        best_account = Sales.find_best_account(
                            service_id=service_id,
                            months_requested=months
                        )

                        if best_account:
                            logger.info(f"    Mejor cuenta encontrada: {best_account.email} (Perfil: {best_account.profile})")
                            # Crear la venta
                            sale_result = Sales.sale_ok(
                                customer=customer,
                                webhook_provider="MercadoPago",
                                payment_type=payment_data.get('payment_type_id', 'unknown'),
                                payment_id=str(payment_id),
                                service_obj=best_account,
                                expiration_date=expiration,
                                unit_price=unit_price,
                                request=request
                            )
                            if sale_result and sale_result[0]:
                                sales_created.append(sale_result[1])
                                logger.info(f"    Venta creada exitosamente: ID {sale_result[1].id}")
                            else:
                                logger.error(f"    Error al crear venta: {sale_result}")
                                profiles_without_stock += 1
                        else:
                            logger.warning(f"    No hay cuentas disponibles para servicio {service_id}")
                            profiles_without_stock += 1
                    except Exception as e:
                        logger.error(f"    Error al buscar/crear cuenta: {str(e)}", exc_info=True)
                        profiles_without_stock += 1

                # Agregar items sin stock a la lista
                if profiles_without_stock > 0:
                    items_without_stock.append({
                        'service_name': service_name,
                        'months': months,
                        'profiles': profiles_without_stock,
                        'price': unit_price * profiles_without_stock
                    })

            # Si hubo items sin stock, enviar notificaciones por email
            if items_without_stock:
                from adm.functions.resend_notifications import ResendEmail

                customer_info = {
                    'username': customer.username,
                    'email': customer.email,
                    'user_id': customer.id
                }
                payment_info = {
                    'payment_id': payment_id,
                    'amount': payment_data.get('transaction_amount'),
                    'payment_type': payment_data.get('payment_type_id'),
                    'cart_id': cart_id
                }

                # Email al admin
                ResendEmail.notify_no_stock(customer_info, items_without_stock, payment_info)

                # Email al cliente
                product_names = [item['service_name'] for item in items_without_stock]
                if customer.email and customer.email != 'example@example.com':
                    ResendEmail.notify_customer_pending_delivery(
                        customer_email=customer.email,
                        customer_name=customer.username,
                        products=product_names
                    )
                logger.info(f"Emails enviados por {len(items_without_stock)} items sin stock")

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

        # Obtener días de regalo disponibles del usuario
        try:
            user_detail = UserDetail.objects.get(user=self.request.user)
            context['free_days'] = user_detail.free_days
        except UserDetail.DoesNotExist:
            context['free_days'] = 0

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


@require_http_methods(["POST"])
@csrf_exempt
def add_gift_days_to_account(request):
    """
    Agregar días de regalo a una cuenta activa del cliente
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        # Verificar que el usuario esté autenticado
        if not request.user.is_authenticated:
            return JsonResponse({
                'success': False,
                'message': 'Debes iniciar sesión para realizar esta acción'
            }, status=401)

        data = json.loads(request.body)
        account_id = data.get('account_id')

        if not account_id:
            return JsonResponse({
                'success': False,
                'message': 'ID de cuenta no proporcionado'
            }, status=400)

        # Obtener el UserDetail del cliente
        try:
            user_detail = UserDetail.objects.get(user=request.user)
        except UserDetail.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'No se encontró información de usuario'
            }, status=404)

        # Verificar que el cliente tenga días de regalo disponibles
        if user_detail.free_days <= 0:
            return JsonResponse({
                'success': False,
                'message': 'No tienes días de regalo disponibles'
            }, status=400)

        # Obtener la cuenta
        try:
            account = Account.objects.get(pk=account_id)
        except Account.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Cuenta no encontrada'
            }, status=404)

        # Verificar que la cuenta pertenece a una venta activa del usuario
        try:
            sale = Sale.objects.get(
                account=account,
                customer=request.user,
                status=True
            )
        except Sale.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Esta cuenta no te pertenece o no está activa'
            }, status=403)

        # Verificar que la cuenta esté activa (no expirada)
        if sale.expiration_date < timezone.now():
            return JsonResponse({
                'success': False,
                'message': 'No puedes agregar días de regalo a una cuenta expirada'
            }, status=400)

        # Agregar los días de regalo a la fecha de expiración de la venta
        days_to_add = user_detail.free_days
        sale.expiration_date = sale.expiration_date + timedelta(days=days_to_add)
        sale.save()

        # También actualizar la fecha de expiración de la cuenta si es necesario
        if account.expiration_date < sale.expiration_date:
            account.expiration_date = sale.expiration_date
            account.save()

        # Resetear los días de regalo del usuario
        user_detail.free_days = 0
        user_detail.save()

        logger.info(f"Usuario {request.user.username} agregó {days_to_add} días de regalo a la cuenta {account_id}")

        return JsonResponse({
            'success': True,
            'message': f'¡Se agregaron {days_to_add} día{"s" if days_to_add > 1 else ""} de regalo a tu cuenta de {account.account_name.description}!',
            'days_added': days_to_add,
            'new_expiration_date': sale.expiration_date.strftime('%d/%m/%Y')
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Datos inválidos'
        }, status=400)
    except Exception as e:
        logger.exception(f"Error al agregar días de regalo: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Error del servidor: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def get_disney_home_code(request):
    """
    Proxy para obtener códigos hogar/código de acceso único de cuentas Disney del usuario autenticado.
    Evita llamadas directas del navegador al proveedor externo (CORS/red).
    """
    try:
        data = json.loads(request.body)
        account_id = data.get('account_id')

        if not account_id:
            return JsonResponse({
                'success': False,
                'message': 'ID de cuenta no proporcionado'
            }, status=400)

        try:
            account = Account.objects.select_related('account_name').get(pk=account_id)
        except Account.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Cuenta no encontrada'
            }, status=404)

        # Validar pertenencia de la cuenta al usuario en una venta activa
        if not Sale.objects.filter(account=account, customer=request.user, status=True).exists():
            return JsonResponse({
                'success': False,
                'message': 'Esta cuenta no te pertenece o no está activa'
            }, status=403)

        # Limitar el uso a cuentas Disney
        service_name = (account.account_name.description or '').lower()
        if 'disney' not in service_name:
            return JsonResponse({
                'success': False,
                'message': 'Esta función solo está disponible para cuentas Disney'
            }, status=400)

        email = (account.email or '').strip()
        if not email:
            return JsonResponse({
                'success': False,
                'message': 'La cuenta no tiene email configurado'
            }, status=400)

        api_url = f'https://servertools.bdpyc.cl/api/home-codes-public/active/{quote(email)}'
        try:
            with urlopen(api_url, timeout=20) as response:
                payload = json.loads(response.read().decode('utf-8'))
        except HTTPError as e:
            return JsonResponse({
                'success': False,
                'message': f'Error del proveedor externo ({e.code})'
            }, status=502)
        except URLError:
            return JsonResponse({
                'success': False,
                'message': 'No se pudo conectar al proveedor de códigos'
            }, status=503)
        except Exception:
            return JsonResponse({
                'success': False,
                'message': 'Respuesta inválida del proveedor de códigos'
            }, status=502)

        return JsonResponse({
            'success': True,
            'email': email,
            'data': payload.get('data', {})
        })
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Datos inválidos'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error del servidor: {str(e)}'
        }, status=500)


def _get_user_active_disney_sale(user, account_id):
    """
    Retorna (sale, account, error_response|None) validando:
    - cuenta existente
    - pertenece al usuario
    - venta activa
    - servicio Disney
    """
    if not account_id:
        return None, None, JsonResponse({
            'success': False,
            'message': 'ID de cuenta no proporcionado'
        }, status=400)

    try:
        sale = Sale.objects.select_related('account__account_name', 'customer').get(
            account_id=account_id,
            customer=user,
            status=True
        )
    except Sale.DoesNotExist:
        return None, None, JsonResponse({
            'success': False,
            'message': 'Esta cuenta no te pertenece o no está activa'
        }, status=403)

    account = sale.account
    service_name = (account.account_name.description or '').lower()
    if 'disney' not in service_name:
        return None, None, JsonResponse({
            'success': False,
            'message': 'Esta función solo está disponible para cuentas Disney'
        }, status=400)

    return sale, account, None


def _can_user_change_disney_account_today(user):
    today = timezone.localdate()
    already_changed = AccountChangeHistory.objects.filter(
        customer=user,
        source='my_account',
        changed_at__date=today
    ).exists()
    return not already_changed


@login_required
@require_http_methods(["POST"])
def disney_change_availability(request):
    """
    Indica si el usuario puede cambiar la cuenta Disney:
    - Solo una vez por día en my_account
    - Debe existir stock del mismo servicio
    """
    try:
        data = json.loads(request.body)
        account_id = data.get('account_id')

        sale, account, error = _get_user_active_disney_sale(request.user, account_id)
        if error:
            return error

        has_stock = Account.objects.filter(
            account_name=account.account_name,
            status=True,
            customer=None,
            external_status='Disponible'
        ).exclude(pk=account.id).exists()

        can_change_today = _can_user_change_disney_account_today(request.user)
        can_change = can_change_today and has_stock

        message = ''
        if not can_change_today:
            message = 'Ya realizaste un cambio hoy desde Mi Cuenta. Inténtalo nuevamente mañana.'
        elif not has_stock:
            message = 'Por el momento no hay cuentas disponibles para cambio inmediato.'

        return JsonResponse({
            'success': True,
            'can_change': can_change,
            'has_stock': has_stock,
            'can_change_today': can_change_today,
            'message': message
        })
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Datos inválidos'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error del servidor: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def disney_change_account(request):
    """
    Cambia la cuenta Disney del usuario:
    - Conserva la duración (expiration_date)
    - Mantiene historial (venta vieja inactiva + venta nueva activa)
    - Libera cuenta vieja para venderse de nuevo
    - Limita a 1 cambio por día en my_account
    """
    try:
        data = json.loads(request.body)
        account_id = data.get('account_id')

        with transaction.atomic():
            sale, old_account, error = _get_user_active_disney_sale(request.user, account_id)
            if error:
                return error

            # Lock de la venta original para evitar doble cambio simultáneo
            sale = Sale.objects.select_for_update().select_related('account__account_name', 'customer').get(pk=sale.pk)
            old_account = Account.objects.select_for_update().get(pk=sale.account_id)

            if not _can_user_change_disney_account_today(request.user):
                return JsonResponse({
                    'success': False,
                    'message': 'Ya realizaste un cambio hoy desde Mi Cuenta. Inténtalo nuevamente mañana.'
                }, status=429)

            new_account = Account.objects.select_for_update().filter(
                account_name=old_account.account_name,
                status=True,
                customer=None,
                external_status='Disponible'
            ).exclude(pk=old_account.id).order_by('profile', 'id').first()

            if not new_account:
                return JsonResponse({
                    'success': False,
                    'message': 'No hay stock disponible para cambiar esta cuenta en este momento.'
                }, status=409)

            # Desactivar de forma robusta cualquier venta activa ligada a la cuenta vieja
            # (incluye el caso esperado de una sola venta activa).
            deactivated_count = Sale.objects.filter(
                customer=sale.customer,
                account=old_account,
                status=True
            ).update(status=False)

            if deactivated_count == 0:
                return JsonResponse({
                    'success': False,
                    'message': 'No se pudo desactivar la venta anterior. Intenta nuevamente.'
                }, status=409)

            payment_method, _ = PaymentMethod.objects.get_or_create(description='Cambio MyAccount')

            new_sale = Sale.objects.create(
                business=sale.business,
                user_seller=request.user,
                customer=sale.customer,
                account=new_account,
                status=True,
                payment_method=payment_method,
                expiration_date=sale.expiration_date,
                payment_amount=0,
                invoice='Cambio MyAccount'
            )

            sale.old_acc = new_sale.id
            sale.save(update_fields=['old_acc'])

            # Liberar cuenta vieja para reventa
            old_account.customer = None
            old_account.status = True
            old_account.modified_by = request.user
            old_account.external_status = 'Disponible'
            old_account.save(update_fields=['customer', 'status', 'modified_by', 'external_status'])

            # Asignar cuenta nueva al cliente
            new_account.customer = sale.customer
            new_account.modified_by = request.user
            new_account.save(update_fields=['customer', 'modified_by'])

            user_phone = None
            try:
                user_phone = sale.customer.userdetail.phone_number
            except Exception:
                user_phone = None

            AccountChangeHistory.objects.create(
                source='my_account',
                customer=sale.customer,
                changed_by=request.user,
                service=old_account.account_name,
                old_sale=sale,
                new_sale=new_sale,
                old_account=old_account,
                new_account=new_account,
                customer_username=sale.customer.username,
                customer_email=sale.customer.email,
                customer_phone=user_phone,
                old_account_email=old_account.email,
                new_account_email=new_account.email,
                old_account_profile=old_account.profile,
                new_account_profile=new_account.profile,
                old_sale_expiration=sale.expiration_date,
                new_sale_expiration=new_sale.expiration_date,
                notes='Cambio automático desde Mi Cuenta por timeout en código de acceso único.'
            )

        return JsonResponse({
            'success': True,
            'message': 'Tu cuenta fue cambiada exitosamente. Se mantuvo la misma duración.',
            'new_account': {
                'service': new_account.account_name.description,
                'email': new_account.email,
                'profile': new_account.profile
            }
        })
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Datos inválidos'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error del servidor: {str(e)}'
        }, status=500)


# WhatsApp Verification Views
from .whatsapp_verification import WhatsAppVerification
from .email_verification import EmailVerification


@require_http_methods(["POST"])
@csrf_exempt
def send_whatsapp_verification(request):
    """
    Send verification code via WhatsApp
    """
    from index.phone_utils import PhoneNumberHandler

    try:
        data = json.loads(request.body)
        phone_number = data.get('phone_number', '').strip()
        country = data.get('country', '').strip()

        if not phone_number or not country:
            return JsonResponse({
                'success': False,
                'message': 'Número de teléfono y país son requeridos'
            }, status=400)

        # Normalizar número según el país
        normalized = PhoneNumberHandler.normalize_phone_by_country(phone_number, country)
        db_number = normalized['db_number']
        full_number = normalized['full_number']

        # Verificar si el número ya está registrado (usando db_number)
        from adm.models import UserDetail
        existing_user = UserDetail.objects.filter(
            phone_number=db_number,
            country=country
        ).first()

        if existing_user:
            return JsonResponse({
                'success': False,
                'message': 'Este número de teléfono ya está registrado'
            }, status=400)

        # Generate and send code (usando db_number para identificar, full_number para enviar)
        code = WhatsAppVerification.generate_verification_code()
        result = WhatsAppVerification.send_verification_code(
            db_number,
            country,
            code,
            full_number_override=full_number
        )

        return JsonResponse(result)

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Datos inválidos'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error del servidor: {str(e)}'
        }, status=500)


@require_http_methods(["POST"])
@csrf_exempt
def verify_whatsapp_code(request):
    """
    Verify WhatsApp code
    """
    from index.phone_utils import PhoneNumberHandler

    try:
        data = json.loads(request.body)
        phone_number = data.get('phone_number', '').strip()
        country = data.get('country', '').strip()
        code = data.get('code', '').strip()

        if not phone_number or not country or not code:
            return JsonResponse({
                'success': False,
                'message': 'Todos los campos son requeridos'
            }, status=400)

        # Normalizar número según el país (para consistencia con el cache)
        normalized = PhoneNumberHandler.normalize_phone_by_country(phone_number, country)
        db_number = normalized['db_number']

        # Verify code (usando db_number)
        result = WhatsAppVerification.verify_code(db_number, country, code)

        return JsonResponse(result)

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Datos inválidos'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error del servidor: {str(e)}'
        }, status=500)


@require_http_methods(["POST"])
@csrf_exempt
def send_whatsapp_login_code(request):
    """
    Send verification code for login via WhatsApp
    """
    from index.phone_utils import PhoneNumberHandler

    try:
        data = json.loads(request.body)
        phone_number = data.get('phone_number', '').strip()
        country = data.get('country', '').strip()
        next_url = data.get('next', '').strip()

        if not phone_number or not country:
            return JsonResponse({
                'success': False,
                'message': 'Número de teléfono y país son requeridos'
            }, status=400)

        # Normalizar número según el país
        normalized = PhoneNumberHandler.normalize_phone_by_country(phone_number, country)
        db_number = normalized['db_number']
        full_number = normalized['full_number']

        # Verificar que el número esté registrado (usando db_number para consulta)
        existing_user = UserDetail.objects.filter(
            phone_number=db_number,
            country=country
        ).first()

        if not existing_user:
            return JsonResponse({
                'success': False,
                'message': 'Este número de teléfono no está registrado. Por favor, regístrate primero.'
            }, status=404)

        # Generate and send code (usando db_number para identificar, full_number para enviar)
        code = WhatsAppVerification.generate_verification_code()
        result = WhatsAppVerification.send_verification_code(
            db_number,
            country,
            code,
            full_number_override=full_number
        )

        # Store login intent in cache (usando db_number como identificador)
        if result['success']:
            login_cache_key = f"whatsapp_login_{country}_{db_number}"
            next_cache_key = f"{login_cache_key}{WHATSAPP_LOGIN_NEXT_CACHE_SUFFIX}"
            safe_next = (
                _sanitize_post_login_redirect(request, next_url)
                or _get_next_from_referer(request)
                or _get_post_login_redirect(request)
            )
            # Compatibilidad amplia entre backends de cache:
            # guardamos valores simples (int/str) en llaves separadas.
            cache.set(login_cache_key, int(existing_user.user.id), timeout=600)  # 10 minutes
            if safe_next:
                cache.set(next_cache_key, safe_next, timeout=600)  # 10 minutes
            else:
                cache.delete(next_cache_key)

        return JsonResponse(result)

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Datos inválidos'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error del servidor: {str(e)}'
        }, status=500)


@require_http_methods(["POST"])
@csrf_exempt
def whatsapp_login_verify_and_auth(request):
    """
    Verify WhatsApp code and authenticate user
    """
    from django.contrib.auth import login
    from index.phone_utils import PhoneNumberHandler

    try:
        data = json.loads(request.body)
        phone_number = data.get('phone_number', '').strip()
        country = data.get('country', '').strip()
        code = data.get('code', '').strip()
        next_url = data.get('next', '').strip()

        if not phone_number or not country or not code:
            return JsonResponse({
                'success': False,
                'message': 'Todos los campos son requeridos'
            }, status=400)

        # Normalizar número según el país (para consistencia con el cache)
        normalized = PhoneNumberHandler.normalize_phone_by_country(phone_number, country)
        db_number = normalized['db_number']

        # Verify code (usando db_number)
        verify_result = WhatsAppVerification.verify_code(db_number, country, code)

        if not verify_result['success']:
            return JsonResponse(verify_result)

        # Get user from login cache (usando db_number)
        login_cache_key = f"whatsapp_login_{country}_{db_number}"
        next_cache_key = f"{login_cache_key}{WHATSAPP_LOGIN_NEXT_CACHE_SUFFIX}"
        login_payload = cache.get(login_cache_key)
        cached_next = str(cache.get(next_cache_key) or '').strip()

        # Normalizar user_id de forma robusta para distintos backends/cache antiguos.
        user_id = None
        if isinstance(login_payload, dict):
            user_id = login_payload.get("user_id")
            if not cached_next:
                cached_next = str(login_payload.get("next") or '').strip()
        elif isinstance(login_payload, int):
            user_id = login_payload
        elif isinstance(login_payload, str):
            stripped = login_payload.strip()
            if stripped.isdigit():
                user_id = int(stripped)
            else:
                try:
                    decoded = json.loads(stripped)
                    if isinstance(decoded, dict):
                        maybe_id = decoded.get("user_id")
                        if isinstance(maybe_id, int):
                            user_id = maybe_id
                        elif isinstance(maybe_id, str) and maybe_id.strip().isdigit():
                            user_id = int(maybe_id.strip())
                        if not cached_next:
                            cached_next = str(decoded.get("next") or '').strip()
                except Exception:
                    user_id = None

        if not user_id:
            return JsonResponse({
                'success': False,
                'message': 'Sesión expirada. Por favor, solicita un nuevo código.'
            }, status=400)

        # Get user and authenticate
        try:
            user = User.objects.get(id=user_id)

            # Authenticate user without password (backend bypass for WhatsApp login)
            from django.contrib.auth import get_backends
            backend = get_backends()[0]
            user.backend = f'{backend.__module__}.{backend.__class__.__name__}'

            login(request, user)

            # Clean up cache
            cache.delete(login_cache_key)
            cache.delete(next_cache_key)

            # Resolver destino posterior al login (prioriza next del flujo actual)
            redirect_url = (
                _sanitize_post_login_redirect(request, next_url)
                or _get_next_from_referer(request)
                or _sanitize_post_login_redirect(request, cached_next)
                or _get_post_login_redirect(request, pop=True)
                or reverse('redirect_on_login')
            )

            return JsonResponse({
                'success': True,
                'message': 'Inicio de sesión exitoso',
                'redirect_url': redirect_url
            })

        except User.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Usuario no encontrado'
            }, status=404)

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Datos inválidos'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error del servidor: {str(e)}'
        }, status=500)


@require_http_methods(["POST"])
@csrf_exempt
@login_required
def send_email_verification(request):
    """
    Send verification code via email for authenticated user.
    """
    try:
        data = json.loads(request.body)
        email = data.get('email', '').strip().lower()

        if not email:
            return JsonResponse({
                'success': False,
                'message': 'El email es requerido'
            }, status=400)

        if '@example.com' in email:
            return JsonResponse({
                'success': False,
                'message': 'Ingresa un email valido'
            }, status=400)

        try:
            validate_email(email)
        except ValidationError:
            return JsonResponse({
                'success': False,
                'message': 'Ingresa un email valido'
            }, status=400)

        existing_user = User.objects.filter(email__iexact=email).exclude(id=request.user.id).first()
        if existing_user:
            return JsonResponse({
                'success': False,
                'message': 'Este email ya esta registrado por otro usuario'
            }, status=400)

        code = EmailVerification.generate_verification_code()
        result = EmailVerification.send_verification_code(request.user.id, email, code)
        return JsonResponse(result)

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Datos invalidos'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error del servidor: {str(e)}'
        }, status=500)


@require_http_methods(["POST"])
@csrf_exempt
@login_required
def verify_email_code(request):
    """
    Verify email code and update authenticated user's email.
    """
    try:
        data = json.loads(request.body)
        email = data.get('email', '').strip().lower()
        code = data.get('code', '').strip()

        if not email or not code:
            return JsonResponse({
                'success': False,
                'message': 'Todos los campos son requeridos'
            }, status=400)

        existing_user = User.objects.filter(email__iexact=email).exclude(id=request.user.id).first()
        if existing_user:
            return JsonResponse({
                'success': False,
                'message': 'Este email ya esta registrado por otro usuario'
            }, status=400)

        if '@example.com' in email:
            return JsonResponse({
                'success': False,
                'message': 'Ingresa un email valido'
            }, status=400)

        try:
            validate_email(email)
        except ValidationError:
            return JsonResponse({
                'success': False,
                'message': 'Ingresa un email valido'
            }, status=400)

        verify_result = EmailVerification.verify_code(request.user.id, email, code)
        if not verify_result.get('success'):
            return JsonResponse(verify_result, status=400)

        previous_email = (request.user.email or '').strip().lower()
        previous_is_placeholder = (not previous_email) or ('@example.com' in previous_email)

        request.user.email = email
        request.user.save(update_fields=['email'])

        days_added = 0
        if previous_is_placeholder:
            user_detail = UserDetail.objects.filter(user=request.user).first()
            if user_detail:
                user_detail.free_days = (user_detail.free_days or 0) + 7
                user_detail.save(update_fields=['free_days'])
                days_added = 7

        message = 'Email verificado y actualizado correctamente'
        if days_added:
            message = f'{message}. Se agregaron {days_added} dias gratis a tu cuenta'

        return JsonResponse({
            'success': True,
            'message': message,
            'days_added': days_added
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Datos invalidos'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error del servidor: {str(e)}'
        }, status=500)


# ============================================
# PayPal Payment Views
# ============================================

@require_http_methods(["POST"])
@csrf_exempt
def paypal_create_order(request):
    """
    Crea una orden de PayPal y devuelve la URL de aprobacion.
    Se llama via AJAX desde el boton de PayPal en el carrito.
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        if not request.user.is_authenticated:
            return JsonResponse({
                'success': False,
                'message': 'Debes iniciar sesion para realizar el pago'
            }, status=401)

        data = json.loads(request.body)
        cart_id = data.get('cart_id')

        if not cart_id:
            return JsonResponse({
                'success': False,
                'message': 'ID de carrito no proporcionado'
            }, status=400)

        # Verificar que el carrito existe
        try:
            cart = IndexCart.objects.get(pk=cart_id)
        except IndexCart.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Carrito no encontrado'
            }, status=404)

        # Preparar items del carrito
        items, subtotal = PayPal.get_cart_items_for_paypal(request)

        if not items:
            return JsonResponse({
                'success': False,
                'message': 'No hay items en el carrito'
            }, status=400)

        # Guardar el cart_id en la sesion para recuperarlo despues
        request.session['paypal_cart_id'] = cart_id

        logger.info(f"PayPal: Orden preparada para carrito {cart_id}, total: {subtotal} MXN")

        # Devolver los datos para que el frontend cree la orden via MCP
        return JsonResponse({
            'success': True,
            'cart_id': cart_id,
            'items': items,
            'subtotal': subtotal,
            'currency': 'MXN'
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Datos invalidos'
        }, status=400)
    except Exception as e:
        logger.exception(f"Error creando orden PayPal: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Error del servidor: {str(e)}'
        }, status=500)


def paypal_success(request):
    """
    Vista de exito despues del pago de PayPal.
    El pago se procesa en el webhook, esta vista solo muestra confirmacion.
    """
    order_id = request.GET.get('token')  # PayPal envia el order ID como 'token'

    # Limpiar el carrito
    cart = CartProcessor(request)
    cart.clear()
    cache.delete('paypal_cart_id')

    return redirect('my_account')


def paypal_cancel(request):
    """
    Vista cuando el usuario cancela el pago de PayPal.
    """
    return redirect('cart')


@csrf_exempt
def paypal_webhook(request):
    """
    Webhook para recibir notificaciones de PayPal.
    Procesa pagos completados y entrega las cuentas al cliente.
    """
    import logging
    logger = logging.getLogger(__name__)

    if request.method != 'POST':
        return HttpResponse(status=405)

    try:
        body = request.body.decode('utf-8')
        data = json.loads(body)

        logger.info(f"PayPal Webhook recibido: {data}")

        event_type = data.get('event_type')

        # Solo procesar pagos completados
        if event_type == 'CHECKOUT.ORDER.APPROVED':
            resource = data.get('resource', {})
            order_id = resource.get('id')
            status = resource.get('status')

            if status != 'APPROVED':
                logger.info(f"Orden PayPal {order_id} no aprobada: {status}")
                return HttpResponse(status=200)

            # Obtener el cart_id de la orden
            # PayPal lo envia en purchase_units[0].reference_id
            purchase_units = resource.get('purchase_units', [])
            if not purchase_units:
                logger.error("Orden sin purchase_units")
                return HttpResponse(status=400)

            cart_id = purchase_units[0].get('reference_id')
            if not cart_id:
                logger.error("Orden sin reference_id (cart_id)")
                return HttpResponse(status=400)

            # Procesar la orden
            return process_paypal_payment(request, cart_id, order_id, resource)

        elif event_type == 'PAYMENT.CAPTURE.COMPLETED':
            # Pago capturado exitosamente
            resource = data.get('resource', {})
            capture_id = resource.get('id')
            logger.info(f"PayPal captura completada: {capture_id}")
            return HttpResponse(status=200)

        # Para otros eventos, solo confirmar recepcion
        return HttpResponse(status=200)

    except json.JSONDecodeError:
        logger.error("Error decodificando JSON del webhook PayPal")
        return HttpResponse(status=400)
    except Exception as e:
        logger.exception(f"Error procesando webhook PayPal: {str(e)}")
        return HttpResponse(status=500)


def process_paypal_payment(request, cart_id, order_id, payment_data):
    """
    Procesa un pago de PayPal aprobado.
    Similar a la logica del webhook de MercadoPago.
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        cart = IndexCart.objects.get(pk=cart_id)
    except IndexCart.DoesNotExist:
        logger.error(f"Carrito {cart_id} no encontrado")
        return HttpResponse(status=404)

    # Verificar si ya fue procesado
    if cart.status_detail == 'approved':
        logger.info(f"Carrito {cart_id} ya fue procesado")
        return HttpResponse(status=200)

    # Actualizar carrito con datos del pago
    cart.payment_id = hash(order_id) % (10 ** 10)  # Convertir a numero
    cart.date_approved = timezone.now()
    cart.payment_type_id = 'paypal'
    cart.status_detail = 'approved'

    # Obtener el monto de purchase_units
    purchase_units = payment_data.get('purchase_units', [])
    if purchase_units:
        amount = purchase_units[0].get('amount', {})
        cart.transaction_amount = float(amount.get('value', 0))
        cart.currency_id = amount.get('currency_code', 'MXN')

    cart.save()

    # Obtener items del carrito
    cart_details = IndexCartdetail.objects.filter(cart=cart)
    customer = cart.customer
    sales_created = []
    items_without_stock = []

    for cart_detail in cart_details:
        service_id = cart_detail.service.id
        service_name = cart_detail.service.description
        months = cart_detail.long
        profiles = cart_detail.quantity
        unit_price = cart_detail.price

        expiration = timezone.now() + timedelta(days=months * 30)

        logger.info(f"PayPal: Procesando {service_name}: {profiles} perfiles x {months} meses")

        profiles_without_stock = 0
        for i in range(profiles):
            try:
                best_account = Sales.find_best_account(
                    service_id=service_id,
                    months_requested=months
                )

                if best_account:
                    sale_result = Sales.sale_ok(
                        customer=customer,
                        webhook_provider="PayPal",
                        payment_type="paypal",
                        payment_id=order_id,
                        service_obj=best_account,
                        expiration_date=expiration,
                        unit_price=unit_price,
                        request=request
                    )
                    if sale_result and sale_result[0]:
                        sales_created.append(sale_result[1])
                        logger.info(f"PayPal: Venta creada: ID {sale_result[1].id}")
                    else:
                        profiles_without_stock += 1
                else:
                    logger.warning(f"PayPal: No hay cuentas para servicio {service_id}")
                    profiles_without_stock += 1
            except Exception as e:
                logger.error(f"PayPal: Error al buscar/crear cuenta: {str(e)}", exc_info=True)
                profiles_without_stock += 1

        if profiles_without_stock > 0:
            items_without_stock.append({
                'service_name': service_name,
                'months': months,
                'profiles': profiles_without_stock,
                'price': unit_price * profiles_without_stock
            })

    # Notificar si hay items sin stock
    if items_without_stock:
        from adm.functions.resend_notifications import ResendEmail

        customer_info = {
            'username': customer.username,
            'email': customer.email,
            'user_id': customer.id
        }
        payment_info = {
            'payment_id': order_id,
            'amount': cart.transaction_amount,
            'payment_type': 'paypal',
            'cart_id': cart_id
        }

        ResendEmail.notify_no_stock(customer_info, items_without_stock, payment_info)

        product_names = [item['service_name'] for item in items_without_stock]
        if customer.email and customer.email != 'example@example.com':
            ResendEmail.notify_customer_pending_delivery(
                customer_email=customer.email,
                customer_name=customer.username,
                products=product_names
            )

    logger.info(f"PayPal: Webhook procesado, {len(sales_created)} ventas para carrito {cart_id}")
    return HttpResponse(status=200)


@require_http_methods(["POST"])
@csrf_exempt
def paypal_capture_order(request):
    """
    Captura una orden de PayPal despues de que el cliente aprueba el pago.
    Se llama desde el frontend despues de que el cliente aprueba en PayPal.
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        data = json.loads(request.body)
        order_id = data.get('order_id')
        cart_id = data.get('cart_id')

        if not order_id or not cart_id:
            return JsonResponse({
                'success': False,
                'message': 'Faltan datos de la orden'
            }, status=400)

        logger.info(f"PayPal: Capturando orden {order_id} para carrito {cart_id}")

        # Verificar que el carrito existe
        try:
            cart = IndexCart.objects.get(pk=cart_id)
        except IndexCart.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Carrito no encontrado'
            }, status=404)

        # Verificar si ya fue procesado
        if cart.status_detail == 'approved':
            return JsonResponse({
                'success': True,
                'message': 'Orden ya procesada',
                'redirect_url': reverse('my_account')
            })

        # Procesar el pago (la captura se hace via MCP desde el frontend)
        # Aqui procesamos la entrega de cuentas

        # Actualizar carrito
        cart.payment_id = hash(order_id) % (10 ** 10)
        cart.date_approved = timezone.now()
        cart.payment_type_id = 'paypal'
        cart.status_detail = 'approved'

        # Obtener el total del carrito de la sesion
        cart.transaction_amount = request.session.get('cart_total', 0)
        cart.currency_id = 'MXN'
        cart.save()

        # Procesar items del carrito
        cart_details = IndexCartdetail.objects.filter(cart=cart)
        customer = cart.customer
        sales_created = []
        items_without_stock = []

        for cart_detail in cart_details:
            service_id = cart_detail.service.id
            service_name = cart_detail.service.description
            months = cart_detail.long
            profiles = cart_detail.quantity
            unit_price = cart_detail.price

            expiration = timezone.now() + timedelta(days=months * 30)

            logger.info(f"PayPal: Procesando {service_name}: {profiles} perfiles x {months} meses")

            profiles_without_stock = 0
            for i in range(profiles):
                try:
                    best_account = Sales.find_best_account(
                        service_id=service_id,
                        months_requested=months
                    )

                    if best_account:
                        sale_result = Sales.sale_ok(
                            customer=customer,
                            webhook_provider="PayPal",
                            payment_type="paypal",
                            payment_id=order_id,
                            service_obj=best_account,
                            expiration_date=expiration,
                            unit_price=unit_price,
                            request=request
                        )
                        if sale_result and sale_result[0]:
                            sales_created.append(sale_result[1])
                            logger.info(f"PayPal: Venta creada: ID {sale_result[1].id}")
                            # Procesar comision de afiliado
                            try:
                                aff_result = procesar_venta_afiliado_desde_carrito(sale_result[1], cart)
                                if aff_result.get('commission'):
                                    logger.info(f"PayPal: Comision de afiliado creada para venta {sale_result[1].id}")
                            except Exception as aff_e:
                                logger.error(f"PayPal: Error procesando afiliado: {str(aff_e)}")
                        else:
                            profiles_without_stock += 1
                    else:
                        logger.warning(f"PayPal: No hay cuentas para servicio {service_id}")
                        profiles_without_stock += 1
                except Exception as e:
                    logger.error(f"PayPal: Error: {str(e)}", exc_info=True)
                    profiles_without_stock += 1

            if profiles_without_stock > 0:
                items_without_stock.append({
                    'service_name': service_name,
                    'months': months,
                    'profiles': profiles_without_stock,
                    'price': unit_price * profiles_without_stock
                })

        # Limpiar codigo de afiliado de la sesion despues de procesar
        if 'affiliate_code' in request.session:
            del request.session['affiliate_code']

        # Notificar si hay items sin stock
        if items_without_stock:
            from adm.functions.resend_notifications import ResendEmail

            customer_info = {
                'username': customer.username,
                'email': customer.email,
                'user_id': customer.id
            }
            payment_info = {
                'payment_id': order_id,
                'amount': cart.transaction_amount,
                'payment_type': 'paypal',
                'cart_id': cart_id
            }

            ResendEmail.notify_no_stock(customer_info, items_without_stock, payment_info)

            product_names = [item['service_name'] for item in items_without_stock]
            if customer.email and customer.email != 'example@example.com':
                ResendEmail.notify_customer_pending_delivery(
                    customer_email=customer.email,
                    customer_name=customer.username,
                    products=product_names
                )

        # Limpiar carrito de la sesion
        cart_processor = CartProcessor(request)
        cart_processor.clear()

        logger.info(f"PayPal: Orden completada, {len(sales_created)} ventas creadas")

        return JsonResponse({
            'success': True,
            'message': 'Pago procesado exitosamente',
            'sales_count': len(sales_created),
            'redirect_url': reverse('my_account')
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Datos invalidos'
        }, status=400)
    except Exception as e:
        logger.exception(f"Error capturando orden PayPal: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Error del servidor: {str(e)}'
        }, status=500)


# ============================================
# Stripe Payment Views
# ============================================

@require_http_methods(["POST"])
@csrf_exempt
def stripe_create_checkout_session(request):
    """
    Crea una sesion de Stripe Checkout y devuelve el session_id.
    Se llama via AJAX desde el boton de Stripe en el carrito.
    """
    import os
    import logging
    logger = logging.getLogger(__name__)

    try:
        if not STRIPE_ENABLED:
            return JsonResponse({
                'success': False,
                'message': 'Stripe esta temporalmente deshabilitado. Usa PayPal para completar tu pago.'
            }, status=503)

        if not request.user.is_authenticated:
            return JsonResponse({
                'success': False,
                'message': 'Debes iniciar sesion para realizar el pago'
            }, status=401)

        data = json.loads(request.body)
        cart_id = data.get('cart_id')

        if not cart_id:
            return JsonResponse({
                'success': False,
                'message': 'ID de carrito no proporcionado'
            }, status=400)

        # Verificar que el carrito existe
        try:
            cart = IndexCart.objects.get(pk=cart_id)
        except IndexCart.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Carrito no encontrado'
            }, status=404)

        # Configurar Stripe
        stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
        site_url = os.environ.get('SITE_URL', 'https://www.cuentasmexico.com')

        # Preparar items del carrito
        cart_session = request.session.get('cart_number')
        if not cart_session:
            return JsonResponse({
                'success': False,
                'message': 'No hay items en el carrito'
            }, status=400)

        # Obtener porcentaje de descuento de la sesión (si hay descuento activo)
        descuento_porcentaje = 0
        if request.session.get('descuento_aplicado', 0) > 0:
            subtotal_original = request.session.get('cart_total', 0)
            if subtotal_original > 0:
                descuento_porcentaje = (request.session.get('descuento_aplicado', 0) / subtotal_original) * 100

        line_items = []
        for item_id, item_data in cart_session.items():
            # Calcular precio por perfil (unitPrice * cantidad de meses)
            item_cost = float(item_data['unitPrice']) * float(item_data['quantity'])

            # Aplicar descuento si existe
            if descuento_porcentaje > 0:
                item_cost = item_cost * (1 - descuento_porcentaje / 100)

            # Stripe espera precios en centavos
            unit_amount_cents = int(round(item_cost * 100))

            # Usar nombres camuflados para pasarelas de pago
            product_id = item_data.get('product_id', item_id)
            masked_name = get_masked_product_name(product_id, item_id)
            masked_description = get_masked_description(
                item_data['profiles'],
                item_data['quantity'],
                product_id
            )

            line_items.append({
                'price_data': {
                    'currency': 'mxn',
                    'product_data': {
                        'name': masked_name[:127],
                        'description': masked_description,
                    },
                    'unit_amount': unit_amount_cents,
                },
                'quantity': int(item_data['profiles']),
            })

        # Crear sesion de checkout con métodos de pago adicionales
        # Incluye: card, oxxo y customer_balance (SPEI/transferencia bancaria)

        # Obtener email del usuario
        user_email = None
        if hasattr(request, 'user') and hasattr(request.user, 'email') and request.user.email:
            user_email = request.user.email

        logger.info(f"Stripe DEBUG - cart_id: {cart_id}")
        logger.info(f"Stripe DEBUG - user_email: {user_email}")
        logger.info(f"Stripe DEBUG - line_items count: {len(line_items)}")

        # Crear o buscar customer en Stripe (requerido para customer_balance/SPEI)
        stripe_customer = None
        if user_email:
            # Buscar si ya existe un customer con ese email
            existing_customers = stripe.Customer.list(email=user_email, limit=1)
            if existing_customers.data:
                stripe_customer = existing_customers.data[0]
                logger.info(f"Stripe DEBUG - Customer existente encontrado: {stripe_customer.id}")
            else:
                # Crear nuevo customer
                stripe_customer = stripe.Customer.create(
                    email=user_email,
                    metadata={
                        'cart_id': str(cart_id),
                        'source': 'checkout_session'
                    }
                )
                logger.info(f"Stripe DEBUG - Nuevo customer creado: {stripe_customer.id}")
        else:
            # Si no hay email, crear customer sin email
            stripe_customer = stripe.Customer.create(
                metadata={
                    'cart_id': str(cart_id),
                    'source': 'checkout_session_anonymous'
                }
            )
            logger.info(f"Stripe DEBUG - Customer anónimo creado: {stripe_customer.id}")

        # Preparar parámetros de la sesión con todos los métodos de pago
        session_params = {
            'customer': stripe_customer.id,
            'payment_method_types': ['card', 'oxxo', 'customer_balance'],
            'payment_method_options': {
                'oxxo': {
                    'expires_after_days': 3,
                },
                'customer_balance': {
                    'funding_type': 'bank_transfer',
                    'bank_transfer': {
                        'type': 'mx_bank_transfer',
                    },
                },
            },
            'line_items': line_items,
            'mode': 'payment',
            'success_url': f"{site_url}/stripe/success/?session_id={{CHECKOUT_SESSION_ID}}",
            'cancel_url': f"{site_url}/stripe/cancel/",
            'metadata': {
                'cart_id': str(cart_id),
            },
            'locale': 'es',
        }

        logger.info(f"Stripe DEBUG - session_params customer: {stripe_customer.id}")

        checkout_session = stripe.checkout.Session.create(**session_params)

        # Guardar información de la sesión en el carrito para pagos diferidos
        cart.stripe_session_id = checkout_session.id
        cart.payment_status = 'awaiting_payment'
        cart.date_created = timezone.now()
        cart.save()

        # Guardar cart_id en la sesion
        request.session['stripe_cart_id'] = cart_id

        logger.info(f"Stripe: Sesion creada {checkout_session.id} para carrito {cart_id}")

        return JsonResponse({
            'success': True,
            'session_id': checkout_session.id,
            'url': checkout_session.url
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Datos invalidos'
        }, status=400)
    except stripe.error.StripeError as e:
        logger.error(f"Stripe ERROR - tipo: {type(e).__name__}")
        logger.error(f"Stripe ERROR - mensaje: {str(e)}")
        logger.error(f"Stripe ERROR - request_id: {getattr(e, 'request_id', 'N/A')}")
        logger.error(f"Stripe ERROR - http_status: {getattr(e, 'http_status', 'N/A')}")
        logger.error(f"Stripe ERROR - code: {getattr(e, 'code', 'N/A')}")
        logger.error(f"Stripe ERROR - param: {getattr(e, 'param', 'N/A')}")
        return JsonResponse({
            'success': False,
            'message': f'Error de Stripe: {str(e)}'
        }, status=500)
    except Exception as e:
        logger.exception(f"Error creando sesion Stripe: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Error del servidor: {str(e)}'
        }, status=500)


def stripe_success(request):
    """
    Vista de exito despues del pago de Stripe.
    Procesa el pago y entrega las cuentas.
    Soporta pagos diferidos: OXXO y transferencia bancaria.
    """
    import os
    import logging
    logger = logging.getLogger(__name__)

    session_id = request.GET.get('session_id')

    if not session_id:
        return redirect('cart')

    try:
        # Configurar Stripe
        stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

        # Obtener la sesion de Stripe
        session = stripe.checkout.Session.retrieve(session_id)

        # Obtener cart_id de los metadata
        cart_id = session.metadata.get('cart_id')
        if not cart_id:
            logger.error("Stripe: Sesion sin cart_id en metadata")
            return redirect('cart')

        # Obtener el carrito
        try:
            cart = IndexCart.objects.get(pk=cart_id)
        except IndexCart.DoesNotExist:
            logger.error(f"Carrito {cart_id} no encontrado")
            return redirect('cart')

        # Verificar estado del pago
        if session.payment_status == 'paid':
            # Pago completado inmediatamente (tarjeta)
            result = process_stripe_payment(request, cart_id, session_id, session)

            # Limpiar el carrito
            cart_processor = CartProcessor(request)
            cart_processor.clear()
            cache.delete('stripe_cart_id')

            return redirect('my_account')

        elif session.payment_status == 'unpaid':
            # Pago diferido (OXXO o transferencia) - mostrar página de espera
            cart.payment_status = 'awaiting_payment'
            cart.stripe_session_id = session_id

            # Detectar tipo de método de pago
            if hasattr(session, 'payment_intent') and session.payment_intent:
                try:
                    payment_intent = stripe.PaymentIntent.retrieve(session.payment_intent)
                    if payment_intent.next_action:
                        next_action = payment_intent.next_action
                        if hasattr(next_action, 'oxxo_display_details'):
                            cart.payment_method_type = 'oxxo'
                            cart.hosted_voucher_url = next_action.oxxo_display_details.hosted_voucher_url
                            if hasattr(next_action.oxxo_display_details, 'expires_after'):
                                from datetime import datetime
                                cart.payment_expires_at = datetime.fromtimestamp(
                                    next_action.oxxo_display_details.expires_after,
                                    tz=timezone.utc
                                )
                        elif hasattr(next_action, 'display_bank_transfer_instructions'):
                            cart.payment_method_type = 'bank_transfer'
                except Exception as e:
                    logger.warning(f"No se pudo obtener detalles de pago diferido: {e}")

            cart.save()

            # Limpiar el carrito de la sesión
            cart_processor = CartProcessor(request)
            cart_processor.clear()

            # Redirigir a la página de estado de pago pendiente
            return redirect('stripe_payment_pending', cart_id=cart_id)

        else:
            logger.warning(f"Stripe: Estado de pago desconocido: {session.payment_status}")
            return redirect('cart')

    except stripe.error.StripeError as e:
        logger.error(f"Error obteniendo sesion de Stripe: {str(e)}")
        return redirect('cart')
    except Exception as e:
        logger.exception(f"Error en stripe_success: {str(e)}")
        return redirect('cart')


def stripe_payment_pending(request, cart_id):
    """
    Vista para mostrar el estado de un pago pendiente (OXXO/transferencia).
    """
    import os
    import logging
    logger = logging.getLogger(__name__)

    try:
        cart = IndexCart.objects.get(pk=cart_id)
    except IndexCart.DoesNotExist:
        return redirect('cart')

    # Verificar que el usuario sea el dueño del carrito
    if cart.customer != request.user:
        return redirect('cart')

    # Obtener detalles del carrito
    cart_details = IndexCartdetail.objects.filter(cart=cart)

    # Configurar Stripe para obtener información actualizada
    stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

    # Obtener información actualizada de la sesión si existe
    voucher_url = cart.hosted_voucher_url
    expires_at = cart.payment_expires_at
    bank_instructions = None

    if cart.stripe_session_id:
        try:
            session = stripe.checkout.Session.retrieve(cart.stripe_session_id)

            # Si ya se pagó, procesar y redirigir
            if session.payment_status == 'paid':
                cart.payment_status = 'approved'
                cart.save()
                process_stripe_payment(request, cart_id, session.id, session)
                return redirect('my_account')

            # Obtener detalles del pago pendiente
            if hasattr(session, 'payment_intent') and session.payment_intent:
                payment_intent = stripe.PaymentIntent.retrieve(session.payment_intent)
                if payment_intent.next_action:
                    next_action = payment_intent.next_action
                    if hasattr(next_action, 'oxxo_display_details'):
                        voucher_url = next_action.oxxo_display_details.hosted_voucher_url
                    elif hasattr(next_action, 'display_bank_transfer_instructions'):
                        bank_instructions = next_action.display_bank_transfer_instructions

        except Exception as e:
            logger.warning(f"Error obteniendo sesión de Stripe: {e}")

    context = {
        'cart': cart,
        'cart_details': cart_details,
        'voucher_url': voucher_url,
        'expires_at': expires_at,
        'bank_instructions': bank_instructions,
        'payment_method': cart.payment_method_type,
    }

    return render(request, 'index/stripe_payment_pending.html', context)


def stripe_cancel(request):
    """
    Vista cuando el usuario cancela el pago de Stripe.
    """
    return redirect('cart')


@csrf_exempt
def stripe_webhook(request):
    """
    Webhook para recibir notificaciones de Stripe.
    Procesa pagos completados y entrega las cuentas al cliente.
    Soporta pagos diferidos: OXXO y transferencia bancaria.
    """
    import os
    import logging
    logger = logging.getLogger(__name__)

    if request.method != 'POST':
        return HttpResponse(status=405)

    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET')

    try:
        # Verificar firma del webhook si hay secret configurado
        if webhook_secret:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
        else:
            # Sin verificacion (solo para desarrollo)
            data = json.loads(payload)
            event = stripe.Event.construct_from(data, stripe.api_key)

        logger.info(f"Stripe Webhook recibido: {event.type}")

        # Manejar el evento
        if event.type == 'checkout.session.completed':
            session = event.data.object
            cart_id = session.metadata.get('cart_id')

            if cart_id:
                try:
                    cart = IndexCart.objects.get(pk=cart_id)
                    # Guardar el tipo de método de pago usado
                    payment_method_types = session.get('payment_method_types', [])
                    if payment_method_types:
                        cart.payment_method_type = payment_method_types[0] if isinstance(payment_method_types, list) else str(payment_method_types)

                    # Procesar según el estado del pago
                    if session.payment_status == 'paid':
                        # Pago completado inmediatamente (tarjeta)
                        cart.payment_status = 'approved'
                        cart.save()
                        process_stripe_payment(request, cart_id, session.id, session)
                    elif session.payment_status == 'unpaid':
                        # Pago diferido (OXXO o transferencia) - esperando pago
                        cart.payment_status = 'awaiting_payment'
                        cart.stripe_session_id = session.id

                        # Para OXXO, obtener la URL del voucher
                        if hasattr(session, 'payment_intent'):
                            try:
                                payment_intent = stripe.PaymentIntent.retrieve(session.payment_intent)
                                if payment_intent.next_action:
                                    next_action = payment_intent.next_action
                                    if hasattr(next_action, 'oxxo_display_details'):
                                        cart.hosted_voucher_url = next_action.oxxo_display_details.hosted_voucher_url
                                        cart.payment_expires_at = timezone.datetime.fromtimestamp(
                                            next_action.oxxo_display_details.expires_after,
                                            tz=timezone.utc
                                        )
                                    elif hasattr(next_action, 'display_bank_transfer_instructions'):
                                        # Transferencia bancaria
                                        cart.payment_method_type = 'bank_transfer'
                            except Exception as e:
                                logger.warning(f"No se pudo obtener next_action: {e}")

                        cart.save()
                        logger.info(f"Stripe: Pago diferido iniciado para carrito {cart_id}")
                except IndexCart.DoesNotExist:
                    logger.error(f"Carrito {cart_id} no encontrado")

        elif event.type == 'checkout.session.async_payment_succeeded':
            # Pago diferido completado (OXXO pagado, transferencia recibida)
            session = event.data.object
            cart_id = session.metadata.get('cart_id')
            if cart_id:
                logger.info(f"Stripe: Pago diferido completado para carrito {cart_id}")
                try:
                    cart = IndexCart.objects.get(pk=cart_id)
                    cart.payment_status = 'approved'
                    cart.save()
                    process_stripe_payment(request, cart_id, session.id, session)
                except IndexCart.DoesNotExist:
                    logger.error(f"Carrito {cart_id} no encontrado")

        elif event.type == 'checkout.session.async_payment_failed':
            # Pago diferido fallido o expirado
            session = event.data.object
            cart_id = session.metadata.get('cart_id')
            if cart_id:
                logger.warning(f"Stripe: Pago diferido fallido para carrito {cart_id}")
                try:
                    cart = IndexCart.objects.get(pk=cart_id)
                    cart.payment_status = 'expired'
                    cart.save()
                except IndexCart.DoesNotExist:
                    logger.error(f"Carrito {cart_id} no encontrado")

        elif event.type == 'payment_intent.succeeded':
            payment_intent = event.data.object
            logger.info(f"Stripe: PaymentIntent exitoso: {payment_intent.id}")

        elif event.type == 'payment_intent.requires_action':
            # El pago requiere acción del cliente (mostrar voucher OXXO, etc.)
            payment_intent = event.data.object
            logger.info(f"Stripe: PaymentIntent requiere acción: {payment_intent.id}")

        # Confirmar recepcion del evento
        return HttpResponse(status=200)

    except ValueError as e:
        logger.error(f"Payload invalido de Stripe webhook: {str(e)}")
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Firma de webhook invalida: {str(e)}")
        return HttpResponse(status=400)
    except Exception as e:
        logger.exception(f"Error procesando webhook Stripe: {str(e)}")
        return HttpResponse(status=500)


def process_stripe_payment(request, cart_id, session_id, session_data):
    """
    Procesa un pago de Stripe completado.
    Similar a la logica del webhook de PayPal/MercadoPago.
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        cart = IndexCart.objects.get(pk=cart_id)
    except IndexCart.DoesNotExist:
        logger.error(f"Carrito {cart_id} no encontrado")
        return False

    # Verificar si ya fue procesado
    if cart.status_detail == 'approved':
        logger.info(f"Carrito {cart_id} ya fue procesado")
        return True

    # Actualizar carrito con datos del pago
    cart.payment_id = hash(session_id) % (10 ** 10)  # Convertir a numero
    cart.date_approved = timezone.now()
    cart.payment_type_id = 'stripe'
    cart.status_detail = 'approved'
    cart.transaction_amount = session_data.amount_total / 100 if hasattr(session_data, 'amount_total') else 0
    cart.currency_id = session_data.currency.upper() if hasattr(session_data, 'currency') else 'MXN'
    cart.save()

    # Obtener items del carrito
    cart_details = IndexCartdetail.objects.filter(cart=cart)
    customer = cart.customer
    sales_created = []
    items_without_stock = []

    for cart_detail in cart_details:
        service_id = cart_detail.service.id
        service_name = cart_detail.service.description
        months = cart_detail.long
        profiles = cart_detail.quantity
        unit_price = cart_detail.price

        expiration = timezone.now() + timedelta(days=months * 30)

        logger.info(f"Stripe: Procesando {service_name}: {profiles} perfiles x {months} meses")

        profiles_without_stock = 0
        for i in range(profiles):
            try:
                best_account = Sales.find_best_account(
                    service_id=service_id,
                    months_requested=months
                )

                if best_account:
                    sale_result = Sales.sale_ok(
                        customer=customer,
                        webhook_provider="Stripe",
                        payment_type="stripe",
                        payment_id=session_id,
                        service_obj=best_account,
                        expiration_date=expiration,
                        unit_price=unit_price,
                        request=request
                    )
                    if sale_result and sale_result[0]:
                        sales_created.append(sale_result[1])
                        logger.info(f"Stripe: Venta creada: ID {sale_result[1].id}")
                        # Procesar comision de afiliado
                        try:
                            aff_result = procesar_venta_afiliado_desde_carrito(sale_result[1], cart)
                            if aff_result.get('commission'):
                                logger.info(f"Stripe: Comision de afiliado creada para venta {sale_result[1].id}")
                        except Exception as aff_e:
                            logger.error(f"Stripe: Error procesando afiliado: {str(aff_e)}")
                    else:
                        profiles_without_stock += 1
                else:
                    logger.warning(f"Stripe: No hay cuentas para servicio {service_id}")
                    profiles_without_stock += 1
            except Exception as e:
                logger.error(f"Stripe: Error al buscar/crear cuenta: {str(e)}", exc_info=True)
                profiles_without_stock += 1

        if profiles_without_stock > 0:
            items_without_stock.append({
                'service_name': service_name,
                'months': months,
                'profiles': profiles_without_stock,
                'price': unit_price * profiles_without_stock
            })

    # Notificar si hay items sin stock
    if items_without_stock:
        from adm.functions.resend_notifications import ResendEmail

        customer_info = {
            'username': customer.username,
            'email': customer.email,
            'user_id': customer.id
        }
        payment_info = {
            'payment_id': session_id,
            'amount': cart.transaction_amount,
            'payment_type': 'stripe',
            'cart_id': cart_id
        }

        ResendEmail.notify_no_stock(customer_info, items_without_stock, payment_info)

        product_names = [item['service_name'] for item in items_without_stock]
        if customer.email and customer.email != 'example@example.com':
            ResendEmail.notify_customer_pending_delivery(
                customer_email=customer.email,
                customer_name=customer.username,
                products=product_names
            )

    logger.info(f"Stripe: Pago procesado, {len(sales_created)} ventas para carrito {cart_id}")
    return True
