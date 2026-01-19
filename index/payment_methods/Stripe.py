# Python
import os
import logging
import stripe

# Django
from django.utils import timezone

# Local
from index.models import IndexCart, IndexCartdetail
from index.payment_methods.utils import get_masked_product_name, get_masked_description

logger = logging.getLogger(__name__)


class StripePayment:
    """
    Clase para manejar pagos con Stripe.
    Utiliza Stripe Checkout para crear sesiones de pago.
    """

    def __init__(self, request):
        self.request = request
        self.site_url = os.environ.get('SITE_URL', 'https://www.cuentasmexico.mx')
        # Stripe credentials
        self.stripe_secret_key = os.environ.get('STRIPE_SECRET_KEY')
        self.stripe_publishable_key = os.environ.get('STRIPE_PUBLISHABLE_KEY')

        # Configurar Stripe con la secret key
        stripe.api_key = self.stripe_secret_key

    def create_checkout_session(self, cart_id):
        """
        Crea una sesion de Stripe Checkout basada en el carrito de la sesion.

        Returns:
            dict: Contiene 'session_id' y 'url' si es exitoso, None si falla.
        """
        cart = self.request.session.get('cart_number')

        if not cart:
            logger.warning("No hay carrito en la sesion")
            return None

        # Obtener porcentaje de descuento de la sesion (si hay descuento activo)
        descuento_porcentaje = 0
        if self.request.session.get('descuento_aplicado', 0) > 0:
            subtotal_original = self.request.session.get('cart_total', 0)
            if subtotal_original > 0:
                descuento_porcentaje = (self.request.session.get('descuento_aplicado', 0) / subtotal_original) * 100

        # Convertir items del carrito al formato de Stripe
        line_items = []

        for item_id, item_data in cart.items():
            # Calcular precio por perfil (unitPrice * cantidad de meses)
            item_cost = float(item_data['unitPrice']) * float(item_data['quantity'])
            
            # Aplicar descuento si existe
            if descuento_porcentaje > 0:
                item_cost = item_cost * (1 - descuento_porcentaje / 100)
            
            # Total de este item (precio por perfil * cantidad de perfiles)
            item_total = item_cost * float(item_data['profiles'])

            # Stripe espera precios en centavos (MXN centavos)
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

        try:
            # Crear sesion de checkout en Stripe
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=line_items,
                mode='payment',
                success_url=f"{self.site_url}/stripe/success/?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{self.site_url}/stripe/cancel/",
                metadata={
                    'cart_id': str(cart_id),
                },
                locale='es',
            )

            logger.info(f"Stripe: Sesion creada {checkout_session.id} para carrito {cart_id}")

            return {
                'session_id': checkout_session.id,
                'url': checkout_session.url,
                'cart_id': cart_id,
            }

        except stripe.error.StripeError as e:
            logger.error(f"Error creando sesion de Stripe: {str(e)}")
            return None

    @staticmethod
    def get_cart_items_for_stripe(request):
        """
        Prepara los items del carrito para crear una sesion de Stripe.

        Returns:
            tuple: (lista de items en formato Stripe, subtotal)
        """
        cart = request.session.get('cart_number')

        if not cart:
            return None, 0

        # Obtener porcentaje de descuento de la sesion (si hay descuento activo)
        descuento_porcentaje = 0
        if request.session.get('descuento_aplicado', 0) > 0:
            subtotal_original = request.session.get('cart_total', 0)
            if subtotal_original > 0:
                descuento_porcentaje = (request.session.get('descuento_aplicado', 0) / subtotal_original) * 100

        items = []
        subtotal = 0

        for item_id, item_data in cart.items():
            # Calcular precio por perfil (unitPrice * cantidad de meses)
            item_cost = float(item_data['unitPrice']) * float(item_data['quantity'])
            
            # Aplicar descuento si existe
            if descuento_porcentaje > 0:
                item_cost = item_cost * (1 - descuento_porcentaje / 100)
            
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
                "name": masked_name[:127],
                "description": masked_description,
                "quantity": item_data['profiles'],
                "itemCost": round(item_cost, 2),
                "itemTotal": round(item_total, 2)
            })

        return items, round(subtotal, 2)

    @staticmethod
    def verify_webhook_signature(payload, sig_header, webhook_secret):
        """
        Verifica la firma del webhook de Stripe.

        Returns:
            dict: Evento de Stripe si es valido, None si falla
        """
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            return event
        except ValueError as e:
            logger.error(f"Payload invalido de Stripe webhook: {str(e)}")
            return None
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Firma de webhook invalida: {str(e)}")
            return None

    @staticmethod
    def retrieve_session(session_id):
        """
        Obtiene los detalles de una sesion de checkout.

        Returns:
            stripe.checkout.Session: Sesion de Stripe
        """
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            return session
        except stripe.error.StripeError as e:
            logger.error(f"Error obteniendo sesion de Stripe: {str(e)}")
            return None
