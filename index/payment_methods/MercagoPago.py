# Python
from datetime import timedelta
import mercadopago
import json
import requests
import os

# Django
from django.utils import timezone

# Local
from index.models import IndexCart, IndexCartdetail
from index.payment_methods.utils import get_masked_product_name, get_masked_description


class MercadoPago():

    def __init__(self, request):
        self.request = request
        self.mp_access_token = os.environ.get('MP_ACCESS_TOKEN')
        self.site_url = os.environ.get('SITE_URL', 'https://www.cuentasmexico.com')

    def Mp_ExpressCheckout(self, cart_id):
        # Validar que el token esté configurado
        if not self.mp_access_token:
            print("WARNING: MP_ACCESS_TOKEN no está configurado en .env")
            return None

        cart = self.request.session.get('cart_number')

        if not cart:
            return None

        new_cart = []
        for item in cart.items():
            # Usar nombres camuflados para pasarelas de pago
            item_id = item[0]
            item_data = item[1]
            product_id = item_data.get('product_id', item_id)
            masked_name = get_masked_product_name(product_id, item_id)
            masked_description = get_masked_description(
                item_data['profiles'],
                item_data['quantity'],
                product_id
            )

            cart_items = {
                "id": str(item_id),  # ID del item para homologación
                "title": masked_name,
                "description": masked_description,
                "category_id": "services",  # Categoría del item para homologación
                "quantity": item_data['profiles'],
                "currency_id": "MXN",
                "unit_price": item_data['unitPrice']*item_data['quantity'],
                "picture_url": f'https://cuentasmexico.com/{item_data["image"]}',
            }
            new_cart.append(cart_items)

        # Inicializa Mercado Pago con variable de entorno
        sdk = mercadopago.SDK(self.mp_access_token)

        # Crea un objeto preference
        preference_data = {
            "items": new_cart,
            "back_urls": {
                "success": f"{self.site_url}/my_account/",
                "failure": f"{self.site_url}/cart",
                "pending": f"{self.site_url}/my_account/"
            },
            "notification_url": f"{self.site_url}/webhook/mercadopago/",
            "statement_descriptor": "CUENTASMEXICO",
            "external_reference": str(cart_id)
        }
        preference_response = sdk.preference().create(preference_data)
        
        # Verificar si hubo error en la respuesta
        status = preference_response.get("status")
        response = preference_response.get("response", {})
        
        if status != 201:
            print(f"ERROR MercadoPago: status={status}, response={response}")
            # Verificar errores comunes
            if "message" in response:
                print(f"MercadoPago message: {response['message']}")
            return None
        
        if 'init_point' not in response:
            print(f"ERROR MercadoPago: 'init_point' no encontrado en response: {response}")
            return None
            
        return response['init_point']

    def search_payments(self, id):
        if not self.mp_access_token:
            return None

        url = f'https://api.mercadopago.com/v1/payments/{id}'
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": "Bearer " + self.mp_access_token
        }
        params = {
            "offset": 0,
            "limit": 10
        }
        response = requests.get(url, headers=headers, params=params)

        payments = json.loads(response.text)
        return payments

    @staticmethod
    def webhook_updater(data):
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

        return cart
