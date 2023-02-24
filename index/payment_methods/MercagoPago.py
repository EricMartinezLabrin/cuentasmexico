# Python
from datetime import timedelta
import mercadopago
import json
import requests
from adm.functions.sales import Sales

# Django
from django.utils import timezone

# Local
from adm.models import Business
from index.models import IndexCart, IndexCartdetail


class MercadoPago():

    def __init__(self, request):
        self.request = request
        self.mp_sdk = Business.objects.get(pk=1).mp_customer_key

    def Mp_ExpressCheckout(self, cart_id):
        cart = self.request.session.get('cart_number')

        if not cart:
            return None

        new_cart = []
        for item in cart.items():
            cart_items = {
                "title": item[1]['name'],
                "quantity": item[1]['profiles'],
                "currency_id": "MXN",
                "unit_price": item[1]['unitPrice']*item[1]['quantity'],
                "picture_url": f'https://cuentasmexico.mx/{item[1]["image"]}',
            }
            new_cart.append(cart_items)

        # Inicializa Mercado Pago
        ck = Business.objects.get(pk=1).mp_customer_key
        # print(ck)
        sdk = mercadopago.SDK(ck)

    #     # Crea un objeto preference
        preference_data = {
            "items": new_cart,
            "back_urls": {
                "success": "https://www.cuentasmexico.mx",
                "failure": "http://www.cuentasmexico.mx",
                "pending": "http://www.cuentasmexico.mx"
            },
            "statement_descriptor": "CUENTASMEXICO",
            "external_reference": cart_id
        }
        preference_response = sdk.preference().create(preference_data)
        preference = preference_response["response"]
        return preference['init_point']

    def search_payments(id):
        url = f'https://api.mercadopago.com/v1/payments/{id}'
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": "Bearer " + "TEST-168801736002262-091119-b7147315b4f642c60178483421325c24-571215114"
        }
        params = {
            "offset": 0,
            "limit": 10
        }
        response = requests.get(url, headers=headers, params=params)

        payments = json.loads(response.text)
        return payments

    def webhook_updater(request, data):
        try:
            # Update Cart
            cart = IndexCart.objects.get(pk=data['external_reference'])
            cart.payment_id = data['collector_id']
            cart.date_created = data['date_created']
            cart.date_approved = data['date_approved']
            cart.date_last_updated = data['date_last_updated']
            cart.money_release_date = data['money_release_date']
            cart.payment_type_id = data['payment_type_id']
            cart.status_detail = data['status_detail']
            cart.currency_id = data['currency_id']
            cart.description = data['description']
            cart.transaction_amount = data['transaction_amount']
            cart.transaction_amount_refunded = data['transaction_amount_refunded']
            cart.coupon_amount = data['coupon_amount']
            cart.save()

            # Find Account.
            cart_data = IndexCartdetail.objects.filter(cart=163)
            for cart_detail in cart_data:
                service_id = cart_detail.service.id
                expiration = timezone.now() + timedelta(days=cart_detail.long*30)
                for i in range(cart_detail.quantity):
                    service = Sales.search_better_acc(
                        service_id=service_id, exp=expiration)
                    sale = Sales.web_sale(request=request, acc=service[1],
                                          unit_price=cart_detail.price, months=cart_detail.long)
            return 200
        except:
            return 404
