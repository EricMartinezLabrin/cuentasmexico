# python
import io
from datetime import datetime
from dateutil.relativedelta import relativedelta

# django
from django.utils import timezone
from django.conf import settings

# models
from adm.models import (
    Affiliate, AffiliateSale, AffiliateCommission,
    AffiliateClick, AffiliateNotification, AffiliateSettings
)


def generar_qr_afiliado(affiliate, size=300):
    """
    Genera un codigo QR con el link de afiliado.

    Args:
        affiliate: Instancia de Affiliate
        size: Tamano del QR en pixeles

    Returns:
        BytesIO buffer con la imagen PNG del QR
    """
    try:
        import qrcode
        from PIL import Image
    except ImportError:
        return None

    # Construir URL del afiliado
    site_url = getattr(settings, 'SITE_URL', 'https://cuentasmexico.com')
    url = f"{site_url}/afiliados/r/{affiliate.codigo_afiliado}/"

    # Crear QR
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    # Crear imagen
    img = qr.make_image(fill_color="black", back_color="white")

    # Redimensionar si es necesario
    if size != 300:
        img = img.resize((size, size), Image.Resampling.LANCZOS)

    # Guardar en buffer
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)

    return buffer


def get_affiliate_link(affiliate):
    """Retorna el link completo de afiliado"""
    site_url = getattr(settings, 'SITE_URL', 'https://cuentasmexico.com')
    return f"{site_url}/afiliados/r/{affiliate.codigo_afiliado}/"


def registrar_clic_afiliado(request, affiliate):
    """
    Registra un clic en el link de afiliado.

    Args:
        request: HttpRequest
        affiliate: Instancia de Affiliate

    Returns:
        AffiliateClick instance
    """
    # Obtener session key
    if not request.session.session_key:
        request.session.create()

    return AffiliateClick.objects.create(
        affiliate=affiliate,
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        referrer=request.META.get('HTTP_REFERER', ''),
        session_key=request.session.session_key
    )


def get_client_ip(request):
    """Obtiene la IP del cliente considerando proxies"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def procesar_venta_afiliado(sale, request):
    """
    Procesa una venta y registra comisiones si hay codigo de afiliado.

    Args:
        sale: Instancia de Sale
        request: HttpRequest

    Returns:
        dict con informacion del procesamiento
    """
    result = {
        'affiliate_sale': None,
        'commission': None,
        'referral_commission': None,
        'error': None
    }

    affiliate_code = request.session.get('affiliate_code')
    if not affiliate_code:
        return result

    try:
        affiliate = Affiliate.objects.get(codigo_afiliado=affiliate_code, status='activo')

        # Evitar auto-comision (el afiliado no puede ganar de sus propias compras)
        if affiliate.user == sale.customer:
            del request.session['affiliate_code']
            return result

        settings_aff = AffiliateSettings.get_settings()

        # Registrar venta de afiliado
        affiliate_sale = AffiliateSale.objects.create(
            affiliate=affiliate,
            sale=sale,
            codigo_usado=affiliate_code
        )
        result['affiliate_sale'] = affiliate_sale

        # Determinar status de la comision
        status = 'aprobada' if affiliate.comision_automatica else 'pendiente'

        # Crear comision directa
        commission = AffiliateCommission.objects.create(
            affiliate=affiliate,
            affiliate_sale=affiliate_sale,
            monto=settings_aff.comision_monto,
            tipo='venta_directa',
            status=status,
            descripcion=f'Venta #{sale.id} - ${sale.payment_amount} MXN'
        )

        if status == 'aprobada':
            commission.fecha_aprobacion = timezone.now()
            commission.save()

        result['commission'] = commission

        # Crear notificacion de venta
        crear_notificacion_afiliado(
            affiliate,
            'venta',
            'Nueva Venta!',
            f'Has generado una venta de ${sale.payment_amount} MXN. Comision: ${settings_aff.comision_monto}',
            '/afiliados/ventas/'
        )

        # Marcar clic como convertido
        session_key = request.session.session_key
        if session_key:
            AffiliateClick.objects.filter(
                affiliate=affiliate,
                session_key=session_key,
                converted=False
            ).update(converted=True)

        # Si tiene referido, crear comision de referido (solo primer mes)
        if affiliate.referido_por and affiliate.fecha_referido:
            limite = affiliate.fecha_referido + relativedelta(months=1)
            if timezone.now() <= limite:
                comision_referido = settings_aff.comision_monto * (settings_aff.porcentaje_comision_referido / 100)

                ref_status = 'aprobada' if affiliate.referido_por.comision_automatica else 'pendiente'

                referral_commission = AffiliateCommission.objects.create(
                    affiliate=affiliate.referido_por,
                    affiliate_sale=affiliate_sale,
                    monto=comision_referido,
                    tipo='referido',
                    status=ref_status,
                    descripcion=f'Comision de referido: {affiliate.codigo_afiliado} - Venta #{sale.id}'
                )

                if ref_status == 'aprobada':
                    referral_commission.fecha_aprobacion = timezone.now()
                    referral_commission.save()

                result['referral_commission'] = referral_commission

                # Notificar al referidor
                crear_notificacion_afiliado(
                    affiliate.referido_por,
                    'referido',
                    'Comision de Referido',
                    f'Tu referido {affiliate.codigo_afiliado} genero una venta. Comision: ${comision_referido:.2f}',
                    '/afiliados/comisiones/'
                )

        # Limpiar sesion
        del request.session['affiliate_code']

    except Affiliate.DoesNotExist:
        result['error'] = 'Codigo de afiliado no encontrado'
        if 'affiliate_code' in request.session:
            del request.session['affiliate_code']
    except Exception as e:
        result['error'] = str(e)

    return result


def crear_notificacion_afiliado(affiliate, tipo, titulo, mensaje, url=None):
    """
    Crea una notificacion interna para el afiliado.

    Args:
        affiliate: Instancia de Affiliate
        tipo: Tipo de notificacion (venta, comision, retiro, referido, sistema)
        titulo: Titulo de la notificacion
        mensaje: Mensaje de la notificacion
        url: URL opcional para redirigir
    """
    return AffiliateNotification.objects.create(
        affiliate=affiliate,
        tipo=tipo,
        titulo=titulo,
        mensaje=mensaje,
        url=url
    )


def aplicar_descuento_afiliado(request, codigo_descuento):
    """
    Verifica y aplica un codigo de descuento de afiliado.

    Args:
        request: HttpRequest
        codigo_descuento: Codigo de descuento a verificar

    Returns:
        dict con resultado: {
            'valido': bool,
            'descuento': Decimal o None,
            'mensaje': str,
            'affiliate': Affiliate o None
        }
    """
    codigo = codigo_descuento.upper().strip()

    try:
        affiliate = Affiliate.objects.get(codigo_descuento=codigo, status='activo')

        # Guardar en sesion para tracking
        request.session['affiliate_code'] = affiliate.codigo_afiliado
        request.session.set_expiry(60 * 60 * 24 * 30)  # 30 dias

        return {
            'valido': True,
            'descuento': affiliate.porcentaje_descuento,
            'mensaje': f'Codigo aplicado: {affiliate.porcentaje_descuento}% de descuento',
            'affiliate': affiliate
        }
    except Affiliate.DoesNotExist:
        return {
            'valido': False,
            'descuento': None,
            'mensaje': 'Codigo no valido',
            'affiliate': None
        }


def procesar_venta_afiliado_desde_carrito(sale, cart):
    """
    Procesa una venta y registra comisiones usando el codigo de afiliado
    guardado en el carrito. Esta funcion se usa desde webhooks donde
    no tenemos acceso a la sesion del usuario.

    Args:
        sale: Instancia de Sale
        cart: Instancia de IndexCart con affiliate_code

    Returns:
        dict con informacion del procesamiento
    """
    result = {
        'affiliate_sale': None,
        'commission': None,
        'referral_commission': None,
        'error': None
    }

    affiliate_code = getattr(cart, 'affiliate_code', None)
    if not affiliate_code:
        return result

    try:
        affiliate = Affiliate.objects.get(codigo_afiliado=affiliate_code, status='activo')

        # Evitar auto-comision (el afiliado no puede ganar de sus propias compras)
        if affiliate.user == sale.customer:
            return result

        settings_aff = AffiliateSettings.get_settings()

        # Registrar venta de afiliado
        affiliate_sale = AffiliateSale.objects.create(
            affiliate=affiliate,
            sale=sale,
            codigo_usado=affiliate_code
        )
        result['affiliate_sale'] = affiliate_sale

        # Determinar status de la comision
        status = 'aprobada' if affiliate.comision_automatica else 'pendiente'

        # Crear comision directa
        commission = AffiliateCommission.objects.create(
            affiliate=affiliate,
            affiliate_sale=affiliate_sale,
            monto=settings_aff.comision_monto,
            tipo='venta_directa',
            status=status,
            descripcion=f'Venta #{sale.id} - ${sale.payment_amount} MXN'
        )

        if status == 'aprobada':
            commission.fecha_aprobacion = timezone.now()
            commission.save()

        result['commission'] = commission

        # Crear notificacion de venta
        crear_notificacion_afiliado(
            affiliate,
            'venta',
            'Nueva Venta!',
            f'Has generado una venta de ${sale.payment_amount} MXN. Comision: ${settings_aff.comision_monto}',
            '/afiliados/ventas/'
        )

        # Si tiene referido, crear comision de referido (solo primer mes)
        if affiliate.referido_por and affiliate.fecha_referido:
            limite = affiliate.fecha_referido + relativedelta(months=1)
            if timezone.now() <= limite:
                comision_referido = settings_aff.comision_monto * (settings_aff.porcentaje_comision_referido / 100)

                ref_status = 'aprobada' if affiliate.referido_por.comision_automatica else 'pendiente'

                referral_commission = AffiliateCommission.objects.create(
                    affiliate=affiliate.referido_por,
                    affiliate_sale=affiliate_sale,
                    monto=comision_referido,
                    tipo='referido',
                    status=ref_status,
                    descripcion=f'Comision de referido: {affiliate.codigo_afiliado} - Venta #{sale.id}'
                )

                if ref_status == 'aprobada':
                    referral_commission.fecha_aprobacion = timezone.now()
                    referral_commission.save()

                result['referral_commission'] = referral_commission

                # Notificar al referidor
                crear_notificacion_afiliado(
                    affiliate.referido_por,
                    'referido',
                    'Comision de Referido',
                    f'Tu referido {affiliate.codigo_afiliado} genero una venta. Comision: ${comision_referido:.2f}',
                    '/afiliados/comisiones/'
                )

    except Affiliate.DoesNotExist:
        result['error'] = 'Codigo de afiliado no encontrado'
    except Exception as e:
        result['error'] = str(e)

    return result


def get_estadisticas_afiliado(affiliate, periodo='mes'):
    """
    Obtiene estadisticas del afiliado para un periodo.

    Args:
        affiliate: Instancia de Affiliate
        periodo: 'semana', 'mes', 'ano', 'total'

    Returns:
        dict con estadisticas
    """
    from django.db.models import Sum, Count
    from django.db.models.functions import TruncDate

    now = timezone.now()

    if periodo == 'semana':
        fecha_inicio = now - relativedelta(days=7)
    elif periodo == 'mes':
        fecha_inicio = now - relativedelta(months=1)
    elif periodo == 'ano':
        fecha_inicio = now - relativedelta(years=1)
    else:  # total
        fecha_inicio = None

    # Filtros base
    ventas_qs = affiliate.ventas.all()
    clics_qs = affiliate.clicks.all()
    comisiones_qs = affiliate.comisiones.all()

    if fecha_inicio:
        ventas_qs = ventas_qs.filter(created_at__gte=fecha_inicio)
        clics_qs = clics_qs.filter(created_at__gte=fecha_inicio)
        comisiones_qs = comisiones_qs.filter(created_at__gte=fecha_inicio)

    # Calcular estadisticas
    total_clics = clics_qs.count()
    total_ventas = ventas_qs.count()
    monto_ventas = ventas_qs.aggregate(
        total=Sum('sale__payment_amount')
    )['total'] or 0

    comisiones_aprobadas = comisiones_qs.filter(status='aprobada').aggregate(
        total=Sum('monto')
    )['total'] or 0

    comisiones_pendientes = comisiones_qs.filter(status='pendiente').aggregate(
        total=Sum('monto')
    )['total'] or 0

    # Tasa de conversion
    tasa_conversion = 0
    if total_clics > 0:
        tasa_conversion = round((total_ventas / total_clics) * 100, 2)

    # Ventas por dia (ultimos 30 dias para grafico)
    ventas_por_dia = affiliate.ventas.filter(
        created_at__gte=now - relativedelta(days=30)
    ).annotate(
        fecha=TruncDate('created_at')
    ).values('fecha').annotate(
        cantidad=Count('id'),
        monto=Sum('sale__payment_amount')
    ).order_by('fecha')

    return {
        'periodo': periodo,
        'total_clics': total_clics,
        'total_ventas': total_ventas,
        'monto_ventas': monto_ventas,
        'comisiones_aprobadas': comisiones_aprobadas,
        'comisiones_pendientes': comisiones_pendientes,
        'tasa_conversion': tasa_conversion,
        'ventas_por_dia': list(ventas_por_dia),
        'balance_disponible': affiliate.balance_disponible,
        'balance_pendiente': affiliate.balance_pendiente,
    }


def calcular_descuento_efectivo(request, servicio, precio_base=None):
    """
    Calcula el descuento efectivo comparando promocion vs afiliado.
    Retorna el mayor de los dos.

    Args:
        request: HttpRequest
        servicio: Objeto Service
        precio_base: Precio base (si None, usa servicio.price)

    Returns:
        dict con:
            - precio_original: Precio sin descuento
            - precio_final: Precio con el mejor descuento aplicado
            - descuento_monto: Monto del descuento
            - descuento_porcentaje: Porcentaje del descuento
            - tipo_descuento: 'promocion', 'afiliado' o None
            - nombre_descuento: Nombre de la promocion o codigo de afiliado
    """
    from adm.functions.promociones import PromocionManager

    if precio_base is None:
        precio_base = servicio.price

    resultado = {
        'precio_original': precio_base,
        'precio_final': precio_base,
        'descuento_monto': 0,
        'descuento_porcentaje': 0,
        'tipo_descuento': None,
        'nombre_descuento': None,
        'tiene_descuento': False,
    }

    # 1. Calcular descuento de promocion
    promo_info = PromocionManager.calcular_precio_con_descuento(servicio, precio_base=precio_base)
    descuento_promo_porcentaje = promo_info.get('porcentaje_descuento', 0)

    # 2. Obtener descuento de afiliado desde sesion
    descuento_afiliado_porcentaje = 0
    codigo_afiliado = None

    affiliate_code = request.session.get('affiliate_code')
    if affiliate_code:
        try:
            affiliate = Affiliate.objects.get(codigo_afiliado=affiliate_code, status='activo')
            descuento_afiliado_porcentaje = float(affiliate.porcentaje_descuento)
            codigo_afiliado = affiliate.codigo_descuento
        except Affiliate.DoesNotExist:
            pass

    # 3. Comparar y aplicar el mayor
    if descuento_promo_porcentaje > 0 or descuento_afiliado_porcentaje > 0:
        resultado['tiene_descuento'] = True

        if descuento_promo_porcentaje >= descuento_afiliado_porcentaje:
            # Promocion gana o son iguales (prioridad a promocion)
            resultado['precio_final'] = promo_info['precio_final']
            resultado['descuento_monto'] = promo_info['descuento_aplicado']
            resultado['descuento_porcentaje'] = descuento_promo_porcentaje
            resultado['tipo_descuento'] = 'promocion'
            resultado['nombre_descuento'] = promo_info.get('promocion_nombre', 'Promocion')
        else:
            # Afiliado gana
            descuento_monto = int(precio_base * (descuento_afiliado_porcentaje / 100))
            resultado['precio_final'] = precio_base - descuento_monto
            resultado['descuento_monto'] = descuento_monto
            resultado['descuento_porcentaje'] = descuento_afiliado_porcentaje
            resultado['tipo_descuento'] = 'afiliado'
            resultado['nombre_descuento'] = f'Codigo {codigo_afiliado}'

    return resultado


def calcular_descuento_carrito(request):
    """
    Calcula el descuento efectivo para todo el carrito.

    Args:
        request: HttpRequest

    Returns:
        dict con:
            - subtotal: Total sin descuento
            - descuento_total: Monto total de descuento
            - total_final: Total con descuento aplicado
            - porcentaje_descuento: Porcentaje promedio de descuento
            - tipo_descuento: 'promocion', 'afiliado' o None
            - nombre_descuento: Nombre del descuento aplicado
            - items: Lista de items con descuento individual
    """
    from adm.models import Service

    cart = request.session.get('cart_number', {})
    subtotal = 0
    descuento_total = 0
    items_con_descuento = []

    # Obtener el mejor descuento global (para simplicidad, usamos porcentaje)
    mejor_descuento_porcentaje = 0
    tipo_descuento = None
    nombre_descuento = None

    # 1. Verificar si hay codigo de afiliado en sesion
    affiliate_code = request.session.get('affiliate_code')
    if affiliate_code:
        try:
            affiliate = Affiliate.objects.get(codigo_afiliado=affiliate_code, status='activo')
            mejor_descuento_porcentaje = float(affiliate.porcentaje_descuento)
            tipo_descuento = 'afiliado'
            nombre_descuento = f'Codigo {affiliate.codigo_descuento}'
        except Affiliate.DoesNotExist:
            pass

    # 2. Verificar promociones activas (obtener el mayor descuento de promocion)
    from adm.functions.promociones import PromocionManager

    for item_id, item_data in cart.items():
        try:
            servicio = Service.objects.get(pk=item_data.get('product_id'))
            promo_info = PromocionManager.calcular_precio_con_descuento(servicio)

            if promo_info['porcentaje_descuento'] > mejor_descuento_porcentaje:
                mejor_descuento_porcentaje = promo_info['porcentaje_descuento']
                tipo_descuento = 'promocion'
                nombre_descuento = promo_info.get('promocion_nombre', 'Promocion')
        except Service.DoesNotExist:
            pass

    # 3. Calcular totales con el mejor descuento
    for item_id, item_data in cart.items():
        precio_item = int(item_data.get('price', 0))
        subtotal += precio_item

        if mejor_descuento_porcentaje > 0:
            descuento_item = int(precio_item * (mejor_descuento_porcentaje / 100))
            descuento_total += descuento_item
            precio_final_item = precio_item - descuento_item
        else:
            descuento_item = 0
            precio_final_item = precio_item

        items_con_descuento.append({
            'id': item_id,
            'nombre': item_data.get('name', ''),
            'precio_original': precio_item,
            'descuento': descuento_item,
            'precio_final': precio_final_item,
        })

    total_final = subtotal - descuento_total

    return {
        'subtotal': subtotal,
        'descuento_total': descuento_total,
        'total_final': total_final,
        'porcentaje_descuento': mejor_descuento_porcentaje,
        'tipo_descuento': tipo_descuento,
        'nombre_descuento': nombre_descuento,
        'tiene_descuento': descuento_total > 0,
        'items': items_con_descuento,
    }
