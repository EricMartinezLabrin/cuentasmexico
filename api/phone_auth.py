import hashlib
import json
import logging
import secrets
from datetime import timedelta

import requests
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from django.db.models import Sum
from django.db import transaction
from django.http import JsonResponse
from django.conf import settings
from django.utils import timezone

from adm.models import Credits, UserDetail
from cupon.models import Shop
from .models import PhoneOtpChallenge, PhoneSession


logger = logging.getLogger(__name__)


OTP_TTL = 300
MAX_OTP_ATTEMPTS = 5
SESSION_TTL = 60 * 60 * 24 * 30


def _api_error(code, detail, status, **extra):
    return JsonResponse({'code': code, 'detail': detail, **extra}, status=status)
INACTIVE_SHOP_MESSAGE = 'Tu tienda no está activa y aprobada. Contacta con nosotros para reactivar tu cuenta.'


def normalize_phone(value):
    digits = ''.join(ch for ch in str(value or '') if ch.isdigit())
    if digits.startswith('52') and len(digits) == 12:
        digits = digits[2:]
    if len(digits) != 10 or not digits.startswith(('2', '3', '4', '5', '6', '7', '8', '9')):
        raise ValueError('phone must be a valid Mexican 10-digit number')
    return f'52{digits}', digits


def _client_ip(request):
    return (request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
            or request.META.get('REMOTE_ADDR'))


def _rate_limit(phone_e164, ip):
    minute_key = f'phone-otp-minute:{phone_e164}'
    if not cache.add(minute_key, 1, 60):
        return 60
    hour_key = f'phone-otp-hour:{phone_e164}'
    hour_count = cache.get(hour_key, 0) + 1
    cache.set(hour_key, hour_count, 3600)
    if hour_count > 5:
        return 3600
    if ip:
        ip_key = f'phone-otp-ip-hour:{ip}'
        ip_count = cache.get(ip_key, 0) + 1
        cache.set(ip_key, ip_count, 3600)
        if ip_count > 30:
            return 3600
    return None


def _find_user(phone_e164, local_phone):
    return (User.objects.select_related('userdetail', 'userdetail__associated_shop')
            .filter(userdetail__phone_number__in=[local_phone, phone_e164])
            .first())


def _shop_is_ready(shop):
    return bool(shop and shop.status and shop.confirmation)


def _require_ready_shop(user):
    try:
        shop = user.userdetail.associated_shop
    except UserDetail.DoesNotExist:
        shop = None
    if not shop:
        return None, JsonResponse({'detail': 'No encontramos una tienda asociada a este teléfono.'}, status=404)
    if not _shop_is_ready(shop):
        return None, JsonResponse({'detail': INACTIVE_SHOP_MESSAGE, 'code': 'SHOP_NOT_ACTIVE_OR_APPROVED'}, status=403)
    return shop, None


def _send_whatsapp_otp(phone_e164, code):
    base_url = (getattr(settings, 'EVO_WHATSAPP_API_URL', '') or '').rstrip('/')
    api_key = getattr(settings, 'EVO_API_KEY', '') or ''
    instance = getattr(settings, 'EVO_INSTANCE', '') or ''
    if not base_url or not api_key or not instance:
        logger.error(
            'OTP Evolution config missing: url=%s key=%s instance=%s',
            bool(base_url), bool(api_key), bool(instance),
        )
        raise RuntimeError('Evolution API is not configured')
    local_phone = phone_e164[2:] if phone_e164.startswith('52') else phone_e164
    whatsapp_number = f'521{local_phone}'
    endpoint = f'{base_url}/message/sendText/{instance}'
    masked_number = f'...{whatsapp_number[-4:]}'
    logger.info('OTP Evolution request: endpoint=%s number=%s', endpoint, masked_number)
    phone_e164 = whatsapp_number
    response = requests.post(
        endpoint,
        headers={'apikey': api_key, 'Content-Type': 'application/json'},
        json={'number': phone_e164, 'text': f'Tu código de acceso es {code}. Expira en 5 minutos. No lo compartas.'},
        timeout=15,
    )
    if response.status_code < 200 or response.status_code >= 300:
        logger.error(
            'OTP Evolution rejected request: status=%s endpoint=%s number=%s body=%s',
            response.status_code,
            endpoint,
            masked_number,
            (response.text or '')[:500],
        )
        raise RuntimeError('Evolution API rejected the message')
    logger.info('OTP Evolution accepted request: status=%s number=%s', response.status_code, masked_number)


def _new_session(user):
    raw_token = secrets.token_urlsafe(48)
    PhoneSession.objects.create(
        user=user,
        token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
        expires_at=timezone.now() + timedelta(seconds=SESSION_TTL),
    )
    return raw_token


def user_from_bearer(request):
    header = request.headers.get('Authorization', '')
    if not header.startswith('Bearer '):
        return None
    token_hash = hashlib.sha256(header[7:].strip().encode()).hexdigest()
    session = (PhoneSession.objects.select_related('user', 'user__userdetail')
               .filter(token_hash=token_hash, revoked_at__isnull=True, expires_at__gt=timezone.now())
               .first())
    return session.user if session else None


def serialize_user(user, shop, token):
    detail = user.userdetail
    balance = Credits.objects.filter(shop=shop).aggregate(total=Sum('credits'))['total'] or 0
    overdue_days = None
    if shop.last_negative_balance_since and balance < 0:
        overdue_days = (timezone.now() - shop.last_negative_balance_since).days
    return {
        'access_token': token,
        'user': {
            'id': user.id, 'name': user.get_full_name() or user.username,
            'email': user.email or None, 'phone': detail.phone_number,
            'password_configured': user.has_usable_password(),
        },
        'shop_info': {
            'shop': {'id': shop.id, 'name': shop.name, 'status': shop.status, 'approved': shop.confirmation, 'phone': shop.phone},
            'balance': balance, 'credit_limit': shop.credit_limit,
            'available_credit': shop.credit_limit + balance,
            'is_overdue': bool(overdue_days is not None and overdue_days >= 7),
            'overdue_days': overdue_days, 'consecutive_on_time_payments': shop.consecutive_on_time_payments,
            'is_shop_owner': detail.is_shop_owner,
        },
    }


def request_otp(request, data):
    try:
        phone_e164, local_phone = normalize_phone(data.get('phone'))
    except ValueError as exc:
        return JsonResponse({'detail': str(exc)}, status=400)
    retry_after = _rate_limit(phone_e164, _client_ip(request))
    if retry_after:
        response = JsonResponse({'detail': 'Demasiadas solicitudes. Intenta más tarde.'}, status=429)
        response['Retry-After'] = str(retry_after)
        return response
    user = _find_user(phone_e164, local_phone)
    if not user:
        return JsonResponse({'detail': 'No encontramos una cuenta con ese teléfono.'}, status=404)
    _, error = _require_ready_shop(user)
    if error:
        return error
    code = f'{secrets.randbelow(1000000):06d}'
    now = timezone.now()
    PhoneOtpChallenge.objects.filter(phone_e164=phone_e164, consumed_at__isnull=True).update(consumed_at=now)
    challenge = PhoneOtpChallenge.objects.create(
        phone_e164=phone_e164, code_hash=make_password(code),
        expires_at=now + timedelta(seconds=OTP_TTL), request_ip=_client_ip(request),
    )
    try:
        _send_whatsapp_otp(phone_e164, code)
    except Exception:
        logger.exception('OTP delivery failed: phone=%s', phone_e164)
        challenge.delete()
        return JsonResponse({'detail': 'No pudimos enviar el código. Intenta más tarde.'}, status=502)
    return JsonResponse({'detail': 'Código enviado por WhatsApp', 'expires_in': OTP_TTL}, status=202)


def verify_otp(request, data):
    try:
        phone_e164, local_phone = normalize_phone(data.get('phone'))
    except ValueError as exc:
        return JsonResponse({'detail': str(exc)}, status=400)
    otp = str(data.get('otp') or '')
    challenge = PhoneOtpChallenge.objects.filter(phone_e164=phone_e164, consumed_at__isnull=True).first()
    if not challenge or challenge.expires_at <= timezone.now() or challenge.attempts >= MAX_OTP_ATTEMPTS:
        return JsonResponse({'detail': 'Código inválido o expirado.'}, status=400)
    if len(otp) != 6 or not check_password(otp, challenge.code_hash):
        challenge.attempts += 1
        challenge.save(update_fields=['attempts'])
        return JsonResponse({'detail': 'Código inválido o expirado.'}, status=400)
    user = _find_user(phone_e164, local_phone)
    if not user:
        return JsonResponse({'detail': 'Cuenta no disponible.'}, status=401)
    shop, error = _require_ready_shop(user)
    if error:
        return error
    with transaction.atomic():
        challenge.consumed_at = timezone.now()
        challenge.save(update_fields=['consumed_at'])
        token = _new_session(user)
    return JsonResponse(serialize_user(user, shop, token), status=200)


def password_login(data):
    try:
        _, local_phone = normalize_phone(data.get('phone'))
    except ValueError as exc:
        return JsonResponse({'detail': str(exc)}, status=400)
    user = _find_user('52' + local_phone, local_phone)
    if not user or not user.has_usable_password() or not check_password(data.get('password') or '', user.password):
        return JsonResponse({'detail': 'Teléfono o contraseña inválidos.'}, status=401)
    shop, error = _require_ready_shop(user)
    if error:
        return error
    return JsonResponse(serialize_user(user, shop, _new_session(user)), status=200)


def set_password(request, data):
    user = user_from_bearer(request)
    if not user:
        return JsonResponse({'detail': 'Sesión inválida o expirada.'}, status=401)
    try:
        validate_password(data.get('password') or '', user=user)
    except ValidationError as exc:
        return JsonResponse({'detail': exc.messages}, status=400)
    user.password = make_password(data['password'])
    user.save(update_fields=['password'])
    return JsonResponse({'password_configured': True}, status=200)


def _contract_response(response, success_code=None):
    try:
        payload = json.loads(response.content.decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        payload = {}
    if success_code:
        payload = {'code': success_code, **payload}
    elif response.status_code == 404:
        detail = str(payload.get('detail', '')).lower()
        code = 'SHOP_NOT_FOUND' if 'tienda' in detail else 'ACCOUNT_NOT_FOUND'
        payload = {'code': code, **payload}
    elif response.status_code == 400:
        detail = str(payload.get('detail', '')).lower()
        code = 'INVALID_PHONE' if 'phone' in detail or 'tel' in detail else 'OTP_INVALID_OR_EXPIRED'
        payload = {'code': code, **payload}
    elif response.status_code == 429:
        retry_after = int(response.get('Retry-After', '60'))
        payload = {'code': 'OTP_RATE_LIMITED', 'retry_after_seconds': retry_after, **payload}
    elif response.status_code == 502:
        payload = {'code': 'OTP_PROVIDER_UNAVAILABLE', **payload}
    elif response.status_code == 401:
        payload = {'code': 'ACCOUNT_NOT_AVAILABLE', **payload}
    result = JsonResponse(payload, status=response.status_code)
    if response.get('Retry-After'):
        result['Retry-After'] = response['Retry-After']
    return result


def request_otp_contract(request, data):
    try:
        phone_e164, local_phone = normalize_phone(data.get('phone'))
    except ValueError as exc:
        return _api_error('INVALID_PHONE', str(exc), 400)
    user = _find_user(phone_e164, local_phone)
    if not user:
        return _api_error('ACCOUNT_NOT_FOUND', 'No encontramos una cuenta con ese telefono.', 404)
    _, error = _require_ready_shop(user)
    if error:
        return _contract_response(error)
    return _contract_response(request_otp(request, data), 'OTP_SENT')


def verify_otp_contract(request, data):
    response = verify_otp(request, data)
    return _contract_response(response, 'SESSION_CREATED' if response.status_code == 200 else None)
