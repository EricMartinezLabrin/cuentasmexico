# Python
import os
import logging

# Django
from django.utils import timezone

# Local
from index.models import IndexCart, IndexCartdetail
from index.payment_methods.utils import get_masked_product_name, get_masked_description

logger = logging.getLogger(__name__)


class PayPal:
    """
    Clase para manejar pagos con PayPal.
    Utiliza el MCP de PayPal para crear ordenes y procesar pagos.
    """

    def __init__(self, request):
        self.request = request
        self.site_url = os.environ.get('SITE_URL', 'https://www.cuentasmexico.mx')
        # PayPal credentials se configuran en el MCP
        self.paypal_client_id = os.environ.get('PAYPAL_CLIENT_ID')
        self.paypal_client_secret = os.environ.get('PAYPAL_CLIENT_SECRET')

    def create_order(self, cart_id):
        """
        Crea una orden de PayPal basada en el carrito de la sesion.

        Returns:
            dict: Contiene 'order_id' y 'approval_url' si es exitoso, None si falla.
        """
        cart = self.request.session.get('cart_number')

        if not cart:
            logger.warning("No hay carrito en la sesion")
            return None

        # Convertir items del carrito al formato de PayPal
        items = []
        subtotal = 0

        for item_id, item_data in cart.items():
            item_cost = float(item_data['unitPrice']) * float(item_data['quantity'])
            item_total = item_cost * float(item_data['profiles'])
            subtotal += item_total

            # Usar nombres camuflados para pasarelas de pago
            product_id = item_data.get('product_id', item_id)
            masked_name = get_masked_product_name(product_id, item_id)
            masked_description = get_masked_description(
                item_data['profiles'],
                item_data['quantity'],
                product_id
            )

            items.append({
                "name": masked_name,
                "description": masked_description,
                "quantity": item_data['profiles'],
                "itemCost": item_cost,
                "itemTotal": item_total
            })

        # La orden se creara via MCP desde la vista
        # Este metodo prepara los datos necesarios
        order_data = {
            "cart_id": cart_id,
            "items": items,
            "subtotal": subtotal,
            "currency": "MXN",
            "return_url": f"{self.site_url}/paypal/success/",
            "cancel_url": f"{self.site_url}/cart",
            "description": f"Orden CuentasMexico #{cart_id}"
        }

        return order_data

    @staticmethod
    def get_cart_items_for_paypal(request):
        """
        Prepara los items del carrito para crear una orden de PayPal.

        Returns:
            list: Lista de items en formato PayPal
        """
        cart = request.session.get('cart_number')

        if not cart:
            return None, 0

        items = []
        subtotal = 0

        for item_id, item_data in cart.items():
            # Calcular precio por perfil (unitPrice * cantidad de meses)
            item_cost = float(item_data['unitPrice']) * float(item_data['quantity'])
            # Total de este item (precio por perfil * cantidad de perfiles)
            item_total = item_cost * float(item_data['profiles'])
            subtotal += item_total

            # Usar nombres camuflados para pasarelas de pago
            product_id = item_data.get('product_id', item_id)
            masked_name = get_masked_product_name(product_id, item_id)
            masked_description = get_masked_description(
                item_data['profiles'],
                item_data['quantity'],
                product_id
            )

            items.append({
                "name": masked_name[:127],  # PayPal limita a 127 caracteres
                "description": masked_description,
                "quantity": item_data['profiles'],
                "itemCost": round(item_cost, 2),
                "itemTotal": round(item_total, 2)
            })

        return items, round(subtotal, 2)
