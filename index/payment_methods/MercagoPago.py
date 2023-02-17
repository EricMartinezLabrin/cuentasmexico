#Python
import mercadopago
import json
import requests

#Django


#Local
from adm.models import Business




class MercadoPago():
    
    def __init__(self, request):
        self.request = request
        self.mp_sdk = Business.objects.get(pk=1).mp_customer_key

    def Mp_ExpressCheckout(self,cart_id):
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
            "external_reference":cart_id
        }
        preference_response = sdk.preference().create(preference_data)
        preference = preference_response["response"]
        return preference['init_point']
    
    def search_payments(self,id):
        url = "https://api.mercadopago.com/v1/payments/"+ id
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": "Bearer " + Business.objects.get(pk=1).mp_customer_key
        }
        params = {
            "offset": 0,
            "limit": 10
        }
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            payments = json.loads(response.text)
            return payments
        else:
            return None

            170
            1700
            85
            1955