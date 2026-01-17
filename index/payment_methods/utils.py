# Utilidades para métodos de pago


def get_masked_product_name(product_id: int, item_id: str = None) -> str:
    """
    Genera un nombre de producto camuflado para enviar a pasarelas de pago.

    El nombre real del servicio no se envía a Stripe/PayPal/MercadoPago,
    en su lugar se envía un código genérico con el ID del producto para
    poder rastrear la compra en nuestro sistema.

    Args:
        product_id: ID del producto/servicio en la base de datos
        item_id: ID del item en el carrito (opcional, para referencia adicional)

    Returns:
        str: Nombre camuflado como "Suscripción Digital #123"
    """
    return f"Suscripción Digital #{product_id}"


def get_masked_description(profiles: int, quantity: int, product_id: int) -> str:
    """
    Genera una descripción camuflada para enviar a pasarelas de pago.

    Args:
        profiles: Número de perfiles/licencias
        quantity: Cantidad de meses
        product_id: ID del producto para referencia

    Returns:
        str: Descripción camuflada sin mencionar el servicio real
    """
    return f"Plan digital - {profiles} licencia(s) x {quantity} mes(es) [Ref: {product_id}]"
