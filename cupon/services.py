from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from adm.models import UserDetail, UserPhoneHistory
from cupon.models import Cupon, CouponRedemption


class CouponRedeemError(Exception):
    pass


def normalize_code(code):
    if not code:
        return ''
    return str(code).strip().lower()


def normalize_phone_number(phone_number):
    if phone_number is None:
        return ''
    return ''.join(ch for ch in str(phone_number) if ch.isdigit())


def phone_key(lada, phone_number):
    normalized = normalize_phone_number(phone_number)
    if not normalized:
        return None
    lada_value = str(lada or '').strip()
    return f'{lada_value}:{normalized}'


def _collect_customer_phones(customer):
    phone_items = set()

    try:
        detail = UserDetail.objects.get(user=customer)
    except UserDetail.DoesNotExist:
        detail = None

    if detail:
        current_key = phone_key(detail.lada, detail.phone_number)
        if current_key and str(detail.phone_number) not in ('0', ''):
            phone_items.add((detail.lada, normalize_phone_number(detail.phone_number), current_key))

        history_qs = UserPhoneHistory.objects.filter(user_detail=detail).only(
            'old_lada', 'old_phone_number', 'new_lada', 'new_phone_number'
        )
        for history in history_qs:
            old_key = phone_key(history.old_lada, history.old_phone_number)
            if old_key and str(history.old_phone_number) not in ('0', ''):
                phone_items.add((history.old_lada, normalize_phone_number(history.old_phone_number), old_key))

            new_key = phone_key(history.new_lada, history.new_phone_number)
            if new_key and str(history.new_phone_number) not in ('0', ''):
                phone_items.add((history.new_lada, normalize_phone_number(history.new_phone_number), new_key))

    return phone_items


def get_customer_verified_phone(customer):
    """
    Retorna el teléfono verificado principal del usuario.
    """
    phones = _collect_customer_phones(customer)
    if not phones:
        return None

    try:
        detail = UserDetail.objects.get(user=customer)
        detail_key = phone_key(detail.lada, detail.phone_number)
        for lada, number, key in phones:
            if key == detail_key:
                return lada, number, key
    except UserDetail.DoesNotExist:
        pass

    # Fallback al primer teléfono disponible si no existe UserDetail usable
    return next(iter(phones))


def validate_coupon_availability(cupon):
    if not cupon.status:
        raise CouponRedeemError('El código está inactivo.')

    if cupon.max_uses > 0 and cupon.used_count >= cupon.max_uses:
        raise CouponRedeemError('El código ya alcanzó el límite de usos.')


def validate_coupon_phone_rule(cupon, customer):
    if not cupon.one_use_per_phone:
        return

    phones = _collect_customer_phones(customer)
    if not phones:
        raise CouponRedeemError('No tienes un teléfono verificado para usar este código.')

    phone_filters = Q()
    for _, _, key in phones:
        phone_filters |= Q(phone_key=key)

    if not phone_filters:
        raise CouponRedeemError('No tienes un teléfono verificado para usar este código.')

    already_used = CouponRedemption.objects.filter(cupon=cupon).filter(phone_filters).exists()
    if already_used:
        raise CouponRedeemError('Este código ya fue usado con tu teléfono y no se puede reutilizar.')


def validate_coupon_for_customer(cupon, customer):
    validate_coupon_availability(cupon)
    validate_coupon_phone_rule(cupon, customer)


def get_coupon_by_name_or_raise(code_name):
    normalized = normalize_code(code_name)
    if not normalized:
        raise CouponRedeemError('El código es obligatorio.')

    try:
        return Cupon.objects.get(name=normalized)
    except Cupon.DoesNotExist:
        raise CouponRedeemError('El código no existe, por favor contacta a tu vendedor.')


def validate_coupon_from_code(code_name, customer):
    cupon = get_coupon_by_name_or_raise(code_name)
    validate_coupon_for_customer(cupon, customer)
    return cupon


@transaction.atomic
def consume_coupon(code_name, customer, seller=None, sale=None, channel=CouponRedemption.CHANNEL_WEB, account=None):
    normalized = normalize_code(code_name)

    try:
        cupon = Cupon.objects.select_for_update().get(name=normalized)
    except Cupon.DoesNotExist:
        raise CouponRedeemError('El código no existe, por favor contacta a tu vendedor.')

    validate_coupon_for_customer(cupon, customer)

    cupon.used_count = F('used_count') + 1
    cupon.used_at = timezone.now()
    if cupon.customer_id is None:
        cupon.customer = customer
    if seller is not None:
        cupon.seller = seller
    if sale is not None:
        cupon.order = sale
    cupon.status_sale = True
    cupon.save(update_fields=['used_count', 'used_at', 'customer', 'seller', 'order', 'status_sale'])
    cupon.refresh_from_db()

    phone_data = get_customer_verified_phone(customer)
    phone_lada = None
    phone_number = None
    phone_identity = None
    if phone_data:
        phone_lada, phone_number, phone_identity = phone_data

    service_name = None
    account_email = None
    profile = None
    payment_amount = cupon.price

    if sale is not None:
        payment_amount = sale.payment_amount
        if getattr(sale, 'account', None):
            service_name = sale.account.account_name.description
            account_email = sale.account.email
            profile = sale.account.profile
    elif account is not None:
        service_name = account.account_name.description
        account_email = account.email
        profile = account.profile

    CouponRedemption.objects.create(
        cupon=cupon,
        customer=customer,
        sale=sale,
        channel=channel,
        service_name=service_name,
        account_email=account_email,
        profile=profile,
        payment_amount=payment_amount,
        duration_unit=cupon.duration_unit,
        duration_quantity=cupon.duration_quantity,
        phone_lada=phone_lada,
        phone_number=phone_number,
        phone_key=phone_identity,
    )

    return cupon
