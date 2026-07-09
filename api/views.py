import csv
from datetime import timedelta, datetime
import base64
import os
import time
from django.db import IntegrityError
from django.forms import model_to_dict
from django.shortcuts import render
from django.contrib.auth import authenticate
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.utils import timezone
from django.contrib.auth.hashers import make_password
from django.db.models import Case, When, Value, CharField, Sum
from django.db import transaction
from django.conf import settings

import json
import stripe
import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
# from pyflowcl import FlowAPI
# from pyflowcl.utils import genera_parametros
from dateutil.relativedelta import relativedelta

from adm.models import Account, Business, Sale, Service, UserDetail, PageVisit, Credits, Bank, PaymentMethod
from cupon.models import Shop
from .functions.notifications import send_push_notification
from .functions.salesApi import SalesApi
from adm.functions.sales import Sales
from adm.functions.send_whatsapp_notification import Notification
from django.db.models import Q

try:
    keys = Business.objects.get(id=1)
    stripe.api_key = keys.stripe_secret_key
    flow_api_key = keys.flow_customer_key
    flow_secret_key = keys.flow_secret_key

except Business.DoesNotExist:
    pass

local_url = 'https://cuentasmexico/api'
pyc_url = 'https://bdpyc.cl/api'

# POST
def _json_body(request):
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return None


def _shop_balance(shop):
    return Credits.objects.filter(shop=shop).aggregate(total=Sum('credits'))['total'] or 0


def _clerk_id_from_request(request, data=None):
    data = data or {}
    return (
        request.headers.get('X-Clerk-User-Id')
        or request.headers.get('Clerk-User-Id')
        or data.get('clerk_id')
        or data.get('clerkId')
    )


def _user_from_clerk(request, data=None):
    clerk_id = _clerk_id_from_request(request, data)
    if not clerk_id:
        return None, JsonResponse(status=401, data={'detail': 'clerk_id is required'})
    try:
        detail = UserDetail.objects.select_related('user', 'associated_shop').get(clerk_id=clerk_id)
        return detail.user, None
    except UserDetail.DoesNotExist:
        return None, JsonResponse(status=401, data={'detail': 'clerk user not registered'})


def _get_or_create_shop_sale_customer(data, seller_user):
    raw_phone = data.get('customer_phone') or data.get('customer_phone_number') or data.get('phone_number')
    phone_number = ''.join(ch for ch in str(raw_phone or '') if ch.isdigit())
    customer_email = (data.get('customer_email') or '').strip()
    customer_name = (data.get('customer_name') or data.get('customer_full_name') or '').strip()
    if not phone_number and not customer_email:
        return seller_user

    lada = ''.join(ch for ch in str(data.get('customer_lada') or data.get('lada') or '52') if ch.isdigit()) or '52'
    local_phone = phone_number[-10:] if len(phone_number) > 10 else phone_number
    username = local_phone or customer_email

    user = User.objects.filter(username=username).first()
    if not user and customer_email:
        user = User.objects.filter(email=customer_email).first()
    if not user:
        user = User.objects.create_user(
            username=username,
            password='api',
            email=customer_email,
            first_name=customer_name,
        )
    else:
        changed = False
        if customer_email and not user.email:
            user.email = customer_email
            changed = True
        if customer_name and not user.first_name:
            user.first_name = customer_name
            changed = True
        if changed:
            user.save()

    business = Business.objects.get(pk=1)
    detail_defaults = {
        'business': business,
        'phone_number': local_phone or '0000000000',
        'lada': int(lada),
        'country': data.get('customer_country') or data.get('country') or 'Mexico',
    }
    UserDetail.objects.update_or_create(user=user, defaults=detail_defaults)
    return user


def api_docs(request):
    return render(request, 'api/docs.html')


def api_schema(request):
    schema_path = os.path.join(settings.BASE_DIR, 'api', 'openapi.json')
    with open(schema_path, 'r', encoding='utf-8') as schema_file:
        return HttpResponse(schema_file.read(), content_type='application/json')


@csrf_exempt
def register_shop_api(request):
    if request.method != 'POST':
        return JsonResponse(status=405, data={'detail': 'method not allowed'})
    data = _json_body(request)
    if data is None:
        return JsonResponse(status=400, data={'detail': 'invalid json'})

    clerk_id = _clerk_id_from_request(request, data)
    name = (data.get('shop_name') or data.get('name') or '').strip()
    owner_name = (data.get('owner') or data.get('owner_name') or data.get('username') or '').strip()
    phone_number = ''.join(ch for ch in str(data.get('phone_number') or data.get('phone') or '') if ch.isdigit())
    email = (data.get('email') or '').strip()
    if not clerk_id or not name or not owner_name or not phone_number:
        return JsonResponse(status=400, data={'detail': 'clerk_id, shop_name, owner and phone_number are required'})

    username = (data.get('username') or email or phone_number or clerk_id).strip()
    base_username = username
    suffix = 1
    while User.objects.filter(username=username).exclude(userdetail__clerk_id=clerk_id).exists():
        suffix += 1
        username = f'{base_username}-{suffix}'

    business = Business.objects.get(pk=1)
    with transaction.atomic():
        user, created = User.objects.get_or_create(
            username=username,
            defaults={'email': email, 'first_name': owner_name}
        )
        if created:
            user.set_unusable_password()
            user.save(update_fields=['password'])
        else:
            changed = False
            if email and user.email != email:
                user.email = email
                changed = True
            if owner_name and not user.first_name:
                user.first_name = owner_name
                changed = True
            if changed:
                user.save()

        shop = Shop.objects.create(
            name=name,
            owner=owner_name,
            phone=phone_number,
            email=email or None,
            giro=(data.get('giro') or 'Distribuidor').strip(),
            address=(data.get('address') or '').strip(),
            city=(data.get('city') or '').strip(),
            cp=data.get('cp') or None,
            seller=user,
            status=False,
            credit_limit=int(data.get('credit_limit') or 300),
            creator_user=user,
        )
        UserDetail.objects.update_or_create(
            user=user,
            defaults={
                'business': business,
                'phone_number': phone_number[-10:] if len(phone_number) > 10 else phone_number,
                'lada': int(data.get('lada') or '52'),
                'country': data.get('country') or 'Mexico',
                'clerk_id': clerk_id,
                'associated_shop': shop,
                'is_shop_owner': True,
            }
        )

    return JsonResponse(status=201, data={
        'detail': 'shop registered',
        'shop': {'id': shop.id, 'name': shop.name, 'status': shop.status, 'credit_limit': shop.credit_limit},
        'user': {'id': user.id, 'username': user.username},
    })


@csrf_exempt
def create_subuser_api(request):
    if request.method != 'POST':
        return JsonResponse(status=405, data={'detail': 'method not allowed'})
    data = _json_body(request)
    if data is None:
        return JsonResponse(status=400, data={'detail': 'invalid json'})
    owner, error = _user_from_clerk(request, data)
    if error:
        return error
    owner_detail = owner.userdetail
    if not owner_detail.associated_shop or not owner_detail.is_shop_owner:
        return JsonResponse(status=403, data={'detail': 'only shop owners can create subusers'})

    sub_clerk_id = data.get('subuser_clerk_id') or data.get('new_clerk_id') or data.get('clerk_id_subuser')
    username = (data.get('username') or data.get('email') or data.get('phone_number') or sub_clerk_id or '').strip()
    phone_number = ''.join(ch for ch in str(data.get('phone_number') or '') if ch.isdigit())
    if not username or not phone_number:
        return JsonResponse(status=400, data={'detail': 'username and phone_number are required'})

    user, created = User.objects.get_or_create(username=username, defaults={'email': data.get('email') or ''})
    if created:
        user.set_unusable_password()
        user.save(update_fields=['password'])

    detail, _ = UserDetail.objects.update_or_create(
        user=user,
        defaults={
            'business': owner_detail.business,
            'phone_number': phone_number[-10:] if len(phone_number) > 10 else phone_number,
            'lada': int(data.get('lada') or '52'),
            'country': data.get('country') or owner_detail.country,
            'clerk_id': sub_clerk_id,
            'associated_shop': owner_detail.associated_shop,
            'is_shop_owner': False,
        }
    )
    return JsonResponse(status=201, data={'detail': 'subuser created', 'user_id': user.id, 'shop_id': detail.associated_shop_id})


@csrf_exempt
def shop_info_api(request):
    if request.method != 'GET':
        return JsonResponse(status=405, data={'detail': 'method not allowed'})
    user, error = _user_from_clerk(request)
    if error:
        return error
    detail = user.userdetail
    shop = detail.associated_shop
    if not shop:
        return JsonResponse(status=404, data={'detail': 'user has no associated shop'})
    balance = _shop_balance(shop)
    overdue_days = None
    if shop.last_negative_balance_since and balance < 0:
        overdue_days = (timezone.now() - shop.last_negative_balance_since).days
    return JsonResponse(status=200, data={
        'shop': {'id': shop.id, 'name': shop.name, 'status': shop.status},
        'balance': balance,
        'credit_limit': shop.credit_limit,
        'available_credit': shop.credit_limit + balance,
        'is_overdue': bool(overdue_days is not None and overdue_days >= 7),
        'overdue_days': overdue_days,
        'consecutive_on_time_payments': shop.consecutive_on_time_payments,
        'is_shop_owner': detail.is_shop_owner,
    })


@csrf_exempt
def sell_account_api(request):
    if request.method != 'POST':
        return JsonResponse(status=405, data={'detail': 'method not allowed'})
    data = _json_body(request)
    if data is None:
        return JsonResponse(status=400, data={'detail': 'invalid json'})
    seller_user, error = _user_from_clerk(request, data)
    if error:
        return error
    detail = seller_user.userdetail
    shop = detail.associated_shop
    if not shop:
        return JsonResponse(status=404, data={'detail': 'user has no associated shop'})
    if not shop.status:
        return JsonResponse(status=403, data={'detail': 'shop is not active'})

    balance = _shop_balance(shop)
    if shop.last_negative_balance_since and balance < 0 and (timezone.now() - shop.last_negative_balance_since).days >= 7:
        return JsonResponse(status=402, data={'detail': 'shop has overdue debt'})

    try:
        service_id = int(data.get('service_id'))
        months = int(data.get('months') or 1)
    except (TypeError, ValueError):
        return JsonResponse(status=400, data={'detail': 'service_id and months must be numeric'})
    if months < 1:
        months = 1

    service = Service.objects.filter(pk=service_id, status=True).first()
    if not service:
        return JsonResponse(status=404, data={'detail': 'service not found'})

    discount = 20 if balance > 0 else 25
    unit_price = max(int(service.price) - discount, 0)
    price = unit_price * months
    projected_balance = balance - price
    if projected_balance < -shop.credit_limit:
        return JsonResponse(status=402, data={'detail': 'insufficient shop credit', 'balance': balance, 'credit_limit': shop.credit_limit})

    account = Sales.find_best_account(service_id, months)
    if not account:
        return JsonResponse(status=404, data={'detail': 'no account available'})

    with transaction.atomic():
        bank, _ = Bank.objects.get_or_create(
            bank_name='Shops',
            defaults={'business': Business.objects.get(pk=1), 'headline': 'Cuentas Mexico', 'card_number': '0', 'clabe': '0'}
        )
        payment_method, _ = PaymentMethod.objects.get_or_create(description='Shop')
        customer = _get_or_create_shop_sale_customer(data, seller_user)
        sale = Sale.objects.create(
            business=Business.objects.get(pk=1),
            user_seller=seller_user,
            bank=bank,
            customer=customer,
            account=account,
            payment_method=payment_method,
            expiration_date=timezone.now() + relativedelta(months=months),
            payment_amount=price,
            invoice=f'SHOP-{shop.id}-{int(time.time())}',
        )
        account.customer = customer
        account.modified_by = seller_user
        account.save(update_fields=['customer', 'modified_by'])
        Credits.objects.create(
            customer=seller_user,
            shop=shop,
            credits=-price,
            detail=f'Venta tienda {service.description} {months} mes(es) a {customer.username}',
        )
        if projected_balance < 0 and not shop.last_negative_balance_since:
            shop.last_negative_balance_since = timezone.now()
            shop.save(update_fields=['last_negative_balance_since'])

    whatsapp_sent = Sales._send_account_delivery_whatsapp(customer, sale)
    return JsonResponse(status=201, data={
        'detail': 'account sold',
        'sale_id': sale.id,
        'service_price': service.price,
        'discount': discount,
        'price': price,
        'unit_price': unit_price,
        'balance': projected_balance,
        'whatsapp_sent': whatsapp_sent,
        'seller': {
            'id': seller_user.id,
            'username': seller_user.username,
            'shop_id': shop.id,
            'shop_name': shop.name,
        },
        'customer': {
            'id': customer.id,
            'username': customer.username,
            'email': customer.email,
        },
        'account': {
            'service': service.description,
            'email': account.email,
            'password': account.password,
            'profile': account.profile,
            'pin': account.pin,
            'expiration_date': sale.expiration_date.isoformat(),
        }
    })


def _b64url_encode(payload: bytes) -> str:
    return base64.urlsafe_b64encode(payload).rstrip(b'=').decode('utf-8')


def _build_google_access_token() -> str:
    service_account_email = os.getenv("GOOGLE_SERVICE_ACCOUNT_EMAIL", "").strip().strip('"')
    private_key = os.getenv("GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY", "").strip().strip('"')

    if not service_account_email or not private_key:
        raise ValueError("Google service account variables missing in .env")

    private_key = private_key.replace("\\n", "\n")

    header = {"alg": "RS256", "typ": "JWT"}
    now = int(time.time())
    claims = {
        "iss": service_account_email,
        "scope": "https://www.googleapis.com/auth/spreadsheets.readonly",
        "aud": "https://oauth2.googleapis.com/token",
        "iat": now,
        "exp": now + 3600,
    }

    encoded_header = _b64url_encode(json.dumps(header, separators=(',', ':')).encode("utf-8"))
    encoded_claims = _b64url_encode(json.dumps(claims, separators=(',', ':')).encode("utf-8"))
    unsigned_jwt = f"{encoded_header}.{encoded_claims}"

    signer = serialization.load_pem_private_key(private_key.encode("utf-8"), password=None)
    signature = signer.sign(
        unsigned_jwt.encode("utf-8"),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    signed_jwt = f"{unsigned_jwt}.{_b64url_encode(signature)}"

    token_res = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": signed_jwt,
        },
        timeout=30,
    )
    if token_res.status_code != 200:
        raise ValueError(f"Google token error: {token_res.text}")

    return token_res.json().get("access_token")


def read_google_sheet_api(request):
    if request.method != "GET":
        return JsonResponse(status=405, data={"detail": "method not allowed"})

    sheet_id = request.GET.get("sheet_id") or os.getenv("SHEETS_PYC_ID") or "1eY2EWKjarh1a909CLSrL22lP5HVUF5CZzdM9SDHBT3M"
    value_range = request.GET.get("range", "").strip() or None

    try:
        access_token = _build_google_access_token()
    except Exception as exc:
        return JsonResponse(status=500, data={"detail": str(exc)})

    metadata_only = request.GET.get("metadata", "").strip().lower() in ("1", "true", "yes")
    if metadata_only:
        metadata_url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}"
        metadata_response = requests.get(
            metadata_url,
            headers={"Authorization": f"Bearer {access_token}"},
            params={"fields": "sheets(properties(title))"},
            timeout=30,
        )
        if metadata_response.status_code != 200:
            return JsonResponse(status=metadata_response.status_code, data={"detail": metadata_response.text})
        payload = metadata_response.json()
        sheet_names = [
            sheet.get("properties", {}).get("title")
            for sheet in payload.get("sheets", [])
            if sheet.get("properties", {}).get("title")
        ]
        return JsonResponse(status=200, data={"spreadsheetId": sheet_id, "sheetNames": sheet_names})

    sheets_url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values:batchGet"
    params = {}
    if value_range:
        params["ranges"] = value_range
    else:
        params["ranges"] = "A1:ZZ1000"

    response = requests.get(
        sheets_url,
        headers={"Authorization": f"Bearer {access_token}"},
        params=params,
        timeout=30,
    )

    if response.status_code != 200:
        return JsonResponse(status=response.status_code, data={"detail": response.text})

    return JsonResponse(status=200, data=response.json())


# POST


# @csrf_exempt
# def checkFlowPaymentByTokenApi(request):
#     url = "https://sandbox.flow.cl/api"
#     route = "/payment/getStatusExtended"
#     apiKey = flow_api_key
#     secretKey = flow_secret_key
#     sandbox = Business.objects.get(id=1).stripe_sandbox
#     if request.method == 'POST':
#         token = request.POST.get('token')
#         if token:
#             api = FlowAPI(flow_key=apiKey, flow_secret=secretKey,
#                           flow_use_sandbox=sandbox)
#             parametros = {"apiKey": api.apiKey, "token": token}
#             # status = api.objetos.call_get_payment_getstatus(
#             #     parameters=genera_parametros(parametros, api.secretKey)
#             # )
#             status = requests.get(
#                 url+route, params=genera_parametros(parametros, api.secretKey))
#             status_decode = status.json()
#             if status_decode["status"] == 2 or status_decode["status"] == "2":
#                 expiration_long = int(status_decode["optional"]["expiration"])
#                 expiration_date = timezone.now() + relativedelta(months=expiration_long)
#                 sale = SalesApi.SalesCreateApi(request, status_decode["payer"], status_decode["optional"]
#                                                ["serviceId"], expiration_date, "flow", status_decode["amount"], status_decode["flowOrder"])
#                 return JsonResponse(status=200, data={"status": "success", "message": "Pago realizado con exito"})
#             else:
#                 return JsonResponse(status=400, data={"status": "error", "message": "Pago no realizado"})
#         else:
#             return JsonResponse(status=400, data={"status": "error", "message": "Token no enviado"})
#     else:
#         return JsonResponse(status=400, data={"status": "error", "message": "Metodo no permitido"})
@csrf_exempt
def changePasswordApi(request):
    if request.method == 'POST':
        data = json.loads(request.body.decode('utf-8'))
        print(data)
        old_password = data['old_password']
        new_password = data['new_password']
        confirm_password = data['confirm_password']
        print(old_password)

        print(new_password)
        print(confirm_password)

        try:
            user = User.objects.get(username=data['user'])
            print(user)
        except User.DoesNotExist:
            return JsonResponse(status=400, data={"status": "error", "message": "Usuario no encontrado."})
        except User.MultipleObjectsReturned:
            return JsonResponse(status=400, data={"status": "error", "message": "Usuario duplicado."})

        # Verificar que la contraseña actual ingresa en coincidencia con la del usuario.
        print(user.check_password(old_password))
        if not user.check_password(old_password):
            print("La contraseña actual no coincide.")
            return JsonResponse(status=400, data={"status": "error", "message": "La contraseña actual no coincide."})

        # Veficar que la contraseña nueva es valida y que coincide con la confirmación.
        if new_password and confirm_password and new_password == confirm_password:
            print("La contraseña nueva coincide.")
            password = make_password(new_password)
            user.password = password
            user.save()
            return JsonResponse(status=200, data={"status": "success", "message": "Contraseña actualizada con éxito."})
        # En caso contrario, notificar al usuario.
        print("La contraseña nueva no coincide.")
        return JsonResponse(status=400, data={"status": "error", "message": "La contraseña nueva no coincide."})


@csrf_exempt
def saleApi(request):
    if request.method == 'POST':
        data = json.loads(request.body.decode('utf-8'))
        expiration_long = data['expiration_long']
        expiration_date = timezone.now() + relativedelta(months=expiration_long)
        customer_username = data['customer_username']
        service_id = data['service_id']
        platform = data['platform']
        amount = data['amount']
        order_id = data['order_id']
        sale = SalesApi.SalesCreateApi(
            request, customer_username, service_id, expiration_date, platform, amount, order_id)

        if sale == False:
            return JsonResponse(status=400, data={"status": "error", "message": "Hubo un error al crear la cuenta, contacta a soporte"})
        else:
            try:
                customer = User.objects.get(username=customer_username)
                customer_detail = UserDetail.objects.get(user=customer)
                if customer_detail.reference_used == False and customer_detail.reference != None:
                    add_days = SalesApi.add_free_days(request,customer.id)
                    if add_days:
                        try:
                            reference = User.objects.get(pk=customer_detail.reference)
                            reference_detail = UserDetail.objects.get(user=reference)
                            send_push_notification(
                                reference_detail.token,"Referido", "Has recibido un referido, encontraras tu recomenza en la sección Mi Cuenta","MyAccount" )
                        except User.DoesNotExist:
                            print("No se encontró el usuario")
                        except User.MultipleObjectsReturned:
                            print("Usuario duplicado")
                        except UserDetail.DoesNotExist:
                            print("No se encontró el detalle del usuario")
                        except UserDetail.MultipleObjectsReturned:
                            print("Detalle de usuario duplicado")
                        except Exception as e:
                            print(e)
                    else:
                        print(add_days)
                return JsonResponse(status=200, data={"status": "success", "message": "Cuenta Creada con Exito"})
            except User.DoesNotExist:
                return JsonResponse(status=400, data={"status": "error", "message": f"Usuario {customer_username} no encontrado."})
            except User.MultipleObjectsReturned:
                return JsonResponse(status=400, data={"status": "error", "message": f"Usuario {customer_username} duplicado."})
    else:
        return JsonResponse(status=400, data={"status": "error", "message": "Metodo no permitido"})
    


@csrf_exempt
def stripe_create_payment(request):
    if request.method == "POST":
        # Decodifica la información en formato JSON a un diccionario Python
        data = json.loads(request.body.decode('utf-8'))
        currency = data.get("currency")
        amount = data.get("amount")

    # Crear el pago en Stripe
    payment_intent = stripe.PaymentIntent.create(
        amount=amount,
        currency=currency,
        # payment_method_types=["card", 'oxxo'],
        automatic_payment_methods={
            'enabled': True,
        },
    )
    # Retornar el client secret generado por Stripe
    return JsonResponse({
        "clientSecret": payment_intent.client_secret
    })


@csrf_exempt
def setToken(request):
    # verificamos si el método HTTP es POST
    if request.method == "POST":
        # obtenemos los datos enviados en el cuerpo de la petición y los convertimos en un diccionario python
        data = json.loads(request.body)
        # obtenemos el valor del campo 'username' del diccionario
        username = data.get('username')
        # obtenemos el valor del campo 'token' del diccionario
        token = data.get('token')

        try:
            # obtenemos un objeto User con el nombre de usuario obtenido
            user = User.objects.get(username=username)
            # obtenemos un objeto UserDetail asociado al objeto User obtenido
            user_detail = UserDetail.objects.get(user=user)

            # comparamos el token almacenado en el objeto UserDetail con el token recibido en la petición
            if user_detail.token != token or user_detail.token is None or user_detail.token == "":
                # si los tokens son diferentes o el token almacenado es None o una cadena vacía,
                # actualizamos el token almacenado en el objeto UserDetail y guardamos los cambios
                user_detail.token = token
                user_detail.save()
                # devolvemos una respuesta HTTP con un código de estado 200 y un diccionario json con el mensaje 'token updated'
                return JsonResponse(status=200, data={'detail': 'token updated'})
            else:
                # si los tokens son iguales, devolvemos una respuesta HTTP con un código de estado 200 y un diccionario json con el mensaje 'token already updated'
                return JsonResponse(status=200, data={'detail': 'token already updated'})

        except User.DoesNotExist:
            # si no encontramos un objeto User con el nombre de usuario obtenido,
            # devolvemos una respuesta HTTP con un código de estado 400 y un diccionario json con el mensaje 'user does not exist'
            return JsonResponse(status=400, data={'detail': 'user does not exist'})

        except UserDetail.DoesNotExist:
            # si no encontramos un objeto UserDetail asociado al objeto User obtenido,
            # creamos uno nuevo con los datos especificados y guardamos los cambios
            UserDetail.objects.create(
                business=Business.objects.get(id=1),
                user=user,
                phone_number="0000000000",
                lada=0,
                country="México",
                token=token
            )
            # devolvemos una respuesta HTTP con un código de estado 200 y un diccionario json con el mensaje 'token updated'
            return JsonResponse(status=200, data={'detail': 'token updated'})

    else:
        # si el método HTTP no es POST, devolvemos una respuesta HTTP con un código de estado 405 y un diccionario json con el mensaje 'method not allowed'
        return JsonResponse(status=405, data={'detail': 'method not allowed'})


@csrf_exempt
# Definir función de envío de notificaciones HTTP con request
def sendNotification(request):
    # Comprobar si el método de solicitud es POST
    if request.method == 'POST':
        # Cargar los datos de clientes en JSON desde el cuerpo del request
        customers = json.loads(request.body)
        # Crear lista vacía para almacenar las respuestas
        response = []
        # Recorrer cada uno de los clientes
        for customer in customers:
            print(customer)
            # Guardar el token del cliente
            token = customer["token"]
            # Guardar el título de la notificación del cliente
            title = customer["title"]
            # Guardar el cuerpo del mensaje
            body = customer["body"]
            # Guardar los datos adicionales necesarios
            url = customer["url"]

            if customer["data"]:
                data = customer["data"]
            else:
                data = {}

            # Enviar notificación push HTTP al cliente
            request = send_push_notification(token, title, body, url, data)
            # Agregar la respuesta a la lista de respuestas
            response.append(request)
        # Devolver una respuesta de éxito con los detalles y respuestas
        return JsonResponse(status=200, data={'detail': "Notifications sent successfully", "response": response})
    # Si el método de solicitud no es POST, devolver un error "Método no permitido"
    else:
        return JsonResponse(status=405, data={'detail': 'method not allowed'})


@csrf_exempt
def create_user_api(request):
    if request.method == "POST":
        data = json.loads(request.body)
        username = data.get('username')
        password = data.get('password')
        email = data.get('email')
        user = User.objects.create_user(
            username=username, password=password, email=email)
        user.save()
        return JsonResponse(status=200, data={'detail': 'user created'})
    else:
        return JsonResponse(status=405, data={'detail': 'method not allowed'})

@csrf_exempt
def use_free_days_api(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        try:
            user = User.objects.get(username = data['user'])
            days_to_add = int(data['days'])
            account_to_update = Account.objects.get(pk=data['account_id'])
            sale_to_extend = Sale.objects.get(account=account_to_update, status=True)
            user_detail = UserDetail.objects.get(user=user)
            days_left = user_detail.free_days
        except User.DoesNotExist:
            return JsonResponse(status=400, data={'detail':'user not found'})
        except UserDetail.DoesNotExist:
            return JsonResponse(status=400, data={'detail':'This user does not have details'})
        except Account.DoesNotExist:
            return JsonResponse(status=400,data={'detail': 'Account does not exist'})
        except Sale.DoesNotExist:
            return JsonResponse(status=400, data={'detail': 'This account does not have a sale'})
        
        if days_to_add <= days_left:
            sale_to_extend.expiration_date = sale_to_extend.expiration_date + timedelta(days=days_to_add)
            sale_to_extend.save()

            user_detail.free_days = user_detail.free_days - days_to_add
            user_detail.save()

            return JsonResponse(status=200, data={'detail':'Success','account': sale_to_extend.account.email, 'new_expiration': sale_to_extend.expiration_date, 'days_left':user_detail.free_days})
    else:
        return JsonResponse(status=405, data={'detail': 'method not allowed'})


@csrf_exempt
def register_user_api(request):
    if request.method == "POST":
        data = json.loads(request.body)
        username = data.get('username')
        password = data.get('password')
        email = data.get('email')
        phone_number = data.get('phone_number')
        country = data.get('country')
        reference = data.get('reference')
        print(reference)
        try:
            user = User.objects.create_user(
                username=username, password=password, email=email)
            user.save()
            user_detail = UserDetail.objects.create(
                user=user, phone_number=phone_number, country=country, reference=reference, business= Business.objects.get(id=1), lada=0
            )
            if country:
                with open('adm/db/paises.csv') as country_list:
                    reader = csv.reader(country_list)
                    for row in reader:
                        if row[0] == country:
                            user_detail.lada = row[5]
                            user_detail.save()
                            break
            return JsonResponse(status=200, data={'detail': 'user created'})
        except IntegrityError:
            return JsonResponse(status=400, data={'detail': 'user already exists'})

    else:
        return JsonResponse(status=405, data={'detail': 'method not allowed'})



# GET
def get_active_sales_by_user_api(request, customer):
    if request.method == 'GET':
        username = customer[-10:]
        try:
            user_obj = User.objects.get(username=username)
            sales = Sale.objects.filter(status=True, customer=user_obj).values(
            "id",
            "business_id",
            "user_seller_id",
            "bank_id",
            "customer_id",
            "account_id",
            "status",
            "payment_method_id",
            "created_at",
            "expiration_date",
            "payment_amount",
            "invoice",
            "comment",
            "old_acc",
            "account_id__account_name__description",
            "account_id__email",
            "account_id__password",
            "account_id__pin",
            "account_id__profile",
        ).annotate(
            pin_status=Case(
                When(account_id__pin__isnull=True, then=Value('No tiene Pin')),
                default='account_id__pin',
                output_field=CharField(),
            )
        )
            if len(sales) == 0:
                user_detail = UserDetail.objects.get(phone_number=customer[-10:])
                user_obj = User.objects.get(username=user_detail.user)
                sales = Sale.objects.filter(status=True, customer=user_obj).values(
                "id",
                "business_id",
                "user_seller_id",
                "bank_id",
                "customer_id",
                "account_id",
                "status",
                "payment_method_id",
                "created_at",
                "expiration_date",
                "payment_amount",
                "invoice",
                "comment",
                "old_acc",
                "account_id__account_name__description",
                "account_id__email",
                "account_id__password",
                "account_id__pin",
                "account_id__profile",
            ).annotate(
                pin_status=Case(
                    When(account_id__pin__isnull=True, then=Value('No tiene Pin')),
                    default='account_id__pin',
                    output_field=CharField(),
                )
            )
                print(sales)
        except User.DoesNotExist:
            return JsonResponse(status=400, data={'detail': 'user not found'})
        except User.MultipleObjectsReturned:
            return JsonResponse(status=400, data={'detail': 'multiple users found'})
        
        return JsonResponse(status=200, data={'detail': list(sales)})
    else:
        return JsonResponse(status=405, data={'detail': 'method not allowed'})

def getServices(request):
    if request.is_secure():
        protocol = 'https://'
    else:
        protocol = 'http://'

    host = request.get_host()+'/media/'  # '192.168.100.12:8000/media/'
    if request.method == 'GET':
        services = Service.objects.filter(status=True).values(
            "id", "description", "logo", "info", "price")
        for service in services:
            service["logo"] = protocol + host + str(service["logo"])
        return JsonResponse(status=200, data={'detail': list(services)})
    else:
        return JsonResponse(status=405, data={'detail': 'method not allowed'})


def active_services_api(request):
    if request.method != 'GET':
        return JsonResponse(status=405, data={'detail': 'method not allowed'})

    services = []
    for service in Service.objects.filter(status=True).order_by('description'):
        logo = ''
        if service.logo:
            logo = service.logo.url
            if logo.startswith('/'):
                logo = request.build_absolute_uri(logo)
        services.append({
            'id': service.id,
            'name': service.description,
            'logo': logo,
            'price': service.price,
            'available_stock': Account.objects.filter(
                account_name=service,
                status=True,
                customer=None,
                external_status='Disponible',
            ).count(),
        })
    return JsonResponse(status=200, data={'detail': services})


def loginApi(request, username, password):
    """
    El siguiente código es una función llamada loginApi que recibe tres parámetros request, username y password. 
    La función se encarga de autenticar al usuario y, si la autenticación es correcta, retorna un objeto JSON con la 
    información del usuario y algunos detalles adicionales. 
    """
    # autenticamos al usuario con las credenciales proporcionadas
    user = authenticate(username=username, password=password)

    # si el usuario es autenticado correctamente
    if user is not None:
        # Creamos un diccionario user_dict con algunos detalles del usuario
        user_dict = {"id":user.id,"username": user.username, "first_name": user.first_name,
                     "last_name": user.last_name, "email": user.email}

        # Obtenemos los detalles adicionales del usuario y los agregamos a una lista
        user_detail = list(UserDetail.objects.filter(user=user.id).values(
            "phone_number", "lada", "country", "free_days"))

        # retornamos un objeto JsonResponse con los detalles del usuario autenticado
        return JsonResponse(status=200, data={'user': user_dict, 'detail': user_detail})

    # si la autenticación es inválida
    else:
        # retornamos un objeto JsonResponse con un mensaje de error
        return JsonResponse(status=400, data={'detail': 'invalid username or password'})


def getActiveAccounts(request):
    """
    El siguiente código busca obtener cuentas activas de un usuario autenticado mediante una solicitud (request) de tipo GET.
    """
    if request.method == 'GET':  # Verificar si la solicitud es GET
        # Obtener los datos de autorización de la solicitud
        data = json.loads(request.headers['Authorization'])
        # Obtener el nombre de usuario del objeto de datos de autorización
        username = data.get('username')
        # Obtener la contraseña del objeto de datos de autorización
        password = data.get('password')
        # Autenticar el username y la contraseña con authenticate()
        auth = authenticate(username=username, password=password)
        if auth is not None:  # Verificar si la autenticación tuvo éxito
            # Obtener las ventas asociadas a la cuenta autenticada y las informaciónes de las cuentas
            sales = Sale.objects.filter(status=True, customer=auth).values("account__id","account__account_name__description", "account__account_name__logo",
                                                                           "account__email", "account__password", "account__pin", "account__profile", "expiration_date")
            # Devolver las ventas de la cuenta autenticada
            return JsonResponse(status=200, data={'detail': list(sales)})
        else:
            # Devolver un error si la autenticación no fue exitosa
            return JsonResponse(status=400, data={'detail': 'invalid username or password'})
    else:
        # Devolver un error si la solicitud no fue GET
        return JsonResponse(status=405, data={'detail': 'method not allowed'})


def get_keys(request):
    if request.method == "GET":
        try:
            keys = Business.objects.get(id=1)
        except Business.DoesNotExist:
            return JsonResponse(status=400, data={"status": "error", "message": "No se encontraron las llaves"})
        return JsonResponse(status=200, data={"status": "success", "message": "Llaves encontradas", "data": {"stripe_api_key": keys.stripe_customer_key, "flow_api_key": keys.flow_customer_key, "flow_secret_key": keys.flow_secret_key, "flow_show": keys.flow_show, "stripe_sandbox": keys.stripe_sandbox}})


def get_services_by_name_api(request, name):
    if request.is_secure():
        protocol = 'https://'
    else:
        protocol = 'http://'

    # '192.168.100.12:8000/media/'  # request.get_host()
    host = request.get_host()+'/media/'
    if request.method == 'GET':
        services = Service.objects.filter(description__icontains=name, status=True).values(
            "id", "description", "logo", "info", "price")
        for service in services:
            service["logo"] = protocol + host + str(service["logo"])
        return JsonResponse(status=200, data={'detail': list(services)})
    else:
        return JsonResponse(status=405, data={'detail': 'method not allowed'})


def get_free_days_api(request):
    # Verifica si el método de solicitud es GET
    if request.method == 'GET':
        # Obtiene el nombre de usuario de los parámetros de la solicitud
        username = request.GET.get('username')
        try:
            # Obtiene un usuario que coincida con el nombre de usuario
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            # Si no existe un usuario con ese nombre, devuelve una respuesta 400 con un mensaje de error
            return JsonResponse(status=400, data={'detail': 'user not found'})
        except User.MultipleObjectsReturned:
            # Si hay más de un usuario que coincida con el nombre, devuelve una respuesta 400 con un mensaje de error.
            return JsonResponse(status=400, data={'detail': 'multiple users found'})
        try:
            # Obtiene los detalles del usuario, como los días libres
            user_detail = UserDetail.objects.get(user=user)
        except UserDetail.DoesNotExist:
            # Si los detalles del usuario no existen, devuelve una respuesta 400 con un mensaje de error
            return JsonResponse(status=400, data={'detail': 'user detail not found'})
        except UserDetail.MultipleObjectsReturned:
            # Si hay múltiples detalles de usuario que coinciden, devuelve una respuesta 400 con un mensaje de error
            return JsonResponse(status=400, data={'detail': 'multiple user details found'})
        # Si todo va bien, devuelve una respuesta 200 con los días libres asociados al usuario.
        return JsonResponse(status=200, data={'detail': user_detail.free_days})


def get_countries_api(request):
    with open('adm/db/paises.csv') as csv_file:
        csv_reader = csv.reader(csv_file)
        data = []
        for row in csv_reader:
            data.append(row[0])
        return JsonResponse({'detail': data})
    
def auto_update_password_api(request):
    """
    API endpoint for automatically updating account passwords.

    Args:
        request (HttpRequest): The HTTP request object.

    Returns:
        JsonResponse: A JSON response indicating the status of the password update process.

    Raises:
        None

    """
    if request.method == 'GET':
        try:
            service = Service.objects.get(id=21)
            accounts = Account.objects.filter(account_name=service)
        except Service.DoesNotExist:
            return JsonResponse(status=400, data={"status": "error", "message": "No se encontraron las llaves"})  
        except Account.DoesNotExist:
            return JsonResponse(status=400, data={"status": "error", "message": "No se encontraron las llaves"})
        except Account.MultipleObjectsReturned:
            return JsonResponse(status=400, data={"status": "error", "message": "No se encontraron las llaves"})
        except Service.MultipleObjectsReturned:
            return JsonResponse(status=400, data={"status": "error", "message": "No se encontraron las llaves"})
        
        success=0
        failed=0

        for account in accounts:
            response = requests.get(f'{pyc_url}/get_password_by_email_api?email={account.email}', verify=False)
            if response.status_code == 200:
                pyc_data = response.json()
                if account.password == pyc_data['password']:
                    print(f"La cuenta {account.email} ya tiene la contraseña actualizada")
                    failed+=1
                    continue
                # print(pyc_data['status'])
                # print(pyc_data['status'] == True)
                if pyc_data['status'] == True:
                    account.status=1
                    account.save()
                    print(f"{pyc_data['Email']}activado")
                if pyc_data['status'] == False:
                    account.status=0
                    account.comment="no"

                    print("desactivado")
                account.password = pyc_data['password']
                print(pyc_data['password'])
                print(account.password)
                account.save()
                success+=1
                print(f"La cuenta {account.email} se actualizó con éxito")
            else:
                failed+=1
                account.status=0
                account.comment="no"
                account.save()
                continue

        return JsonResponse(status=200, data={"status": "Finished","success":success,"failed":failed})

def notify_tomorrows_due_date_api(request):
    """
    API endpoint for notifying users of accounts that are due tomorrow.

    Args:
        request (HttpRequest): The HTTP request object.

    Returns:
        JsonResponse: A JSON response indicating the status of the notification process.

    Raises:
        None

    """
    if request.method == 'GET':
        # Obtener la fecha de mañana
        tomorrow = datetime.now() + timedelta(days=1)
        tomorrow = tomorrow.date()
        today = datetime.now().date()
        # Obtener todas las ventas que vencen mañana
        sales = Sale.objects.filter(
            expiration_date__icontains=tomorrow,
            status=1
        )
        # Crear una lista vacía para almacenar las respuestas
        response = {'day':tomorrow,'success': 0, 'failed': 0, 'pending':[]}
        # Recorrer cada una de las ventas
        for sale in sales:
            # Obtener el token del usuario
            token = sale.customer.userdetail.token
            if token:
                # Crear el título de la notificación
                title = 'Cuenta por vencer'
                # Crear el cuerpo del mensaje
                body = f'Tu cuenta {sale.account.account_name.description} vence mañana'
                # Crear los datos adicionales
                data = {"account_id": sale.account.id}
                # Enviar la notificación push
                request = send_push_notification(token, title, body, 'MyAccount', data)

            message = f'Tu cuenta {sale.account.account_name.description}: {sale.account.email} vence mañana {sale.expiration_date.date()}. Obtén 20% de descuento renovando hoy {datetime.now().date()}'
            lada = sale.customer.userdetail.lada
            phone_number = sale.customer.userdetail.phone_number

            notify = Notification.send_whatsapp_notification(message,lada,phone_number)
            if notify == 200:
                response['success']+=1
            else:
                response['failed']+=1
                response['pending'].append(phone_number)

        Notification.send_whatsapp_notification('Esta es la lista de clientes pendientes por notificar vencimientos de mañana: '+str(response['pending']),52, 8335355863)

            
        # Devolver una respuesta de éxito con los detalles y respuestas
        return JsonResponse(status=200, data={'detail': 'Notifications sent successfully', 'response': response})
    else:
        # Devolver un error si el método de solicitud no es GET
        return JsonResponse(status=405, data={'detail': 'method not allowed'})

def notify_today_due_date_api(request):
    """
    API endpoint for notifying users of accounts that are due tomorrow.

    Args:
        request (HttpRequest): The HTTP request object.

    Returns:
        JsonResponse: A JSON response indicating the status of the notification process.

    Raises:
        None

    """
    if request.method == 'GET':
        # Obtener la fecha de mañana
        today = datetime.now().date()

        # Obtener todas las ventas que vencen mañana
        sales = Sale.objects.filter(
            expiration_date__icontains=today,
            status=1
        )
        # Crear una lista vacía para almacenar las respuestas

        response = {'day':today,'success': 0, 'failed': 0, 'pending':[]}
        # Recorrer cada una de las ventas
        for sale in sales:
            # Obtener el token del usuario
            token = sale.customer.userdetail.token
            if token:
                # Crear el título de la notificación
                title = 'Cuenta por vencer'
                # Crear el cuerpo del mensaje
                body = f'Hola!!! Estamos realizando cortes a los servicios impagos. Podrias quedar sin señal HOY!.'
                # Crear los datos adicionales
                data = {"account_id": sale.account.id}
                # Enviar la notificación push
                request = send_push_notification(token, title, body, 'MyAccount', data)

            message = f'Estamos realizando cortes a los servicios impagos.Tu cuenta {sale.account.account_name.description}: {sale.account.email} podria quedar sin señal HOY!. Obtén 10% de descuento renovando hoy {datetime.now().date()}'
            lada = sale.customer.userdetail.lada
            phone_number = sale.customer.userdetail.phone_number

            notify = Notification.send_whatsapp_notification(message,lada,phone_number)
            if notify == 200:
                response['success']+=1
            else:
                response['failed']+=1
                response['pending'].append(phone_number)

        Notification.send_whatsapp_notification('Esta es la lista de clientes pendientes por notificar vencimientos de hoy: '+str(response['pending']),52, 8335355863)
        # Devolver una respuesta de éxito con los detalles y respuestas
        return JsonResponse(status=200, data={'detail': 'Notifications sent successfully', 'response': response})
    else:
        # Devolver un error si el método de solicitud no es GET
        return JsonResponse(status=405, data={'detail': 'method not allowed'})


@csrf_exempt
def record_service_click(request):
    """
    Endpoint para registrar clics en servicios
    Espera un POST con el ID del servicio
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            service_id = data.get('service_id')
            
            if not service_id:
                return JsonResponse(status=400, data={'detail': 'service_id is required'})
            
            try:
                service = Service.objects.get(id=service_id)
            except Service.DoesNotExist:
                return JsonResponse(status=404, data={'detail': 'Service not found'})
            
            # Obtener información del request
            user = request.user if request.user.is_authenticated else None
            
            # Obtener IP del cliente
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip_address = x_forwarded_for.split(',')[0]
            else:
                ip_address = request.META.get('REMOTE_ADDR')
            
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            referrer = request.META.get('HTTP_REFERER', '')
            session_key = request.session.session_key
            
            # Crear el registro de visita/clic en servicio
            PageVisit.objects.create(
                page='service',
                page_url=f'/service-click/{service_id}/',
                service=service,
                user=user,
                ip_address=ip_address,
                user_agent=user_agent[:500] if user_agent else '',
                referrer=referrer[:500] if referrer else '',
                session_key=session_key
            )
            
            return JsonResponse(status=200, data={'detail': 'Service click recorded successfully'})
        
        except json.JSONDecodeError:
            return JsonResponse(status=400, data={'detail': 'Invalid JSON'})
        except Exception as e:
            return JsonResponse(status=500, data={'detail': str(e)})
    else:
        return JsonResponse(status=405, data={'detail': 'method not allowed'})

