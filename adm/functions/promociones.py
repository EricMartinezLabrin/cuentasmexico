"""
Utilidades para gestión de promociones y cálculo de descuentos
"""
from django.utils import timezone
from decimal import Decimal


class PromocionManager:
    """Clase para gestionar promociones y cálculo de precios con descuento"""

    @staticmethod
    def obtener_promocion_activa(servicio):
        """
        Obtiene la promoción activa más relevante para un servicio
        Prioriza por orden: específicos > todos > excepto
        """
        from adm.models import Promocion

        now = timezone.now()

        # Buscar promociones activas
        promociones_activas = Promocion.objects.filter(
            status='activa'
        ).filter(
            # Fecha inicio debe ser nula o menor/igual a ahora
            fecha_inicio__isnull=True
        ) | Promocion.objects.filter(
            status='activa',
            fecha_inicio__lte=now
        )

        # Filtrar por fecha fin
        promociones_activas = promociones_activas.filter(
            fecha_fin__isnull=True
        ) | promociones_activas.filter(
            fecha_fin__gte=now
        )

        # Priorizar por tipo de aplicación
        # 1. Servicios específicos
        promocion = promociones_activas.filter(
            aplicacion='especificos',
            servicios=servicio
        ).first()

        if promocion:
            return promocion

        # 2. Todos los servicios
        promocion = promociones_activas.filter(
            aplicacion='todos'
        ).first()

        if promocion:
            return promocion

        # 3. Todos excepto algunos (si el servicio no está excluido)
        promocion = promociones_activas.filter(
            aplicacion='excepto'
        ).exclude(
            servicios=servicio
        ).first()

        return promocion

    @staticmethod
    def calcular_precio_con_descuento(servicio, cantidad=1, precio_base=None):
        """
        Calcula el precio final de un servicio aplicando las promociones activas

        Args:
            servicio: Objeto Service
            cantidad: Cantidad de servicios a comprar
            precio_base: Precio base a usar (si None, usa service.price)

        Returns:
            dict con información del precio y descuento aplicado
        """
        if precio_base is None:
            precio_base = servicio.price

        precio_original = precio_base
        precio_final = precio_base
        descuento_aplicado = 0
        promocion = None

        # Buscar promoción activa
        promocion_activa = PromocionManager.obtener_promocion_activa(servicio)

        if promocion_activa and promocion_activa.is_active():
            if promocion_activa.aplica_a_servicio(servicio):
                promocion = promocion_activa

                # Aplicar descuento según el tipo
                if promocion.tipo_descuento == 'porcentaje':
                    descuento = precio_base * (float(promocion.porcentaje_descuento) / 100)
                    precio_final = int(precio_base - descuento)
                    descuento_aplicado = int(descuento)

                elif promocion.tipo_descuento == 'monto_fijo':
                    precio_final = max(0, precio_base - promocion.monto_descuento)
                    descuento_aplicado = min(precio_base, promocion.monto_descuento)

                elif promocion.tipo_descuento == 'nxm' and cantidad >= promocion.cantidad_llevar:
                    # LÓGICA CORREGIDA para NxM
                    # Ejemplo 3x2: llevas 3, pagas 2
                    # - cantidad_llevar = 3 (lo que lleva el cliente)
                    # - cantidad_pagar = 2 (lo que paga el cliente)
                    sets_completos = cantidad // promocion.cantidad_llevar
                    items_restantes = cantidad % promocion.cantidad_llevar

                    # Precio por set = precio_base * cantidad_pagar
                    # Ejemplo: $100 * 2 = $200 por cada set de 3
                    precio_por_set = precio_base * promocion.cantidad_pagar
                    precio_total = (sets_completos * precio_por_set) + (items_restantes * precio_base)

                    precio_final = int(precio_total)
                    descuento_aplicado = (precio_base * cantidad) - precio_final

        return {
            'precio_original': precio_original,
            'precio_final': precio_final,
            'descuento_aplicado': descuento_aplicado,
            'tiene_descuento': descuento_aplicado > 0,
            'porcentaje_descuento': int((descuento_aplicado / precio_original * 100)) if precio_original > 0 else 0,
            'promocion': promocion,
            'promocion_nombre': promocion.nombre if promocion else None,
            'promocion_tipo': promocion.get_tipo_descuento_display() if promocion else None,
        }

    @staticmethod
    def obtener_promociones_banner():
        """
        Obtiene todas las promociones activas que deben mostrarse en banners
        Ordenadas por orden_banner
        """
        from adm.models import Promocion

        now = timezone.now()

        promociones = Promocion.objects.filter(
            status='activa',
            mostrar_en_banner=True,
            imagen__isnull=False
        ).filter(
            fecha_inicio__isnull=True
        ) | Promocion.objects.filter(
            status='activa',
            mostrar_en_banner=True,
            imagen__isnull=False,
            fecha_inicio__lte=now
        )

        promociones = promociones.filter(
            fecha_fin__isnull=True
        ) | promociones.filter(
            fecha_fin__gte=now
        )

        return promociones.order_by('orden_banner', '-created_at')

    @staticmethod
    def aplicar_promociones_a_servicios(servicios):
        """
        Aplica promociones a una lista de servicios y retorna la información con precios

        Args:
            servicios: QuerySet o lista de objetos Service

        Returns:
            Lista de diccionarios con información de servicios y promociones
        """
        resultado = []

        for servicio in servicios:
            precio_info = PromocionManager.calcular_precio_con_descuento(servicio)

            resultado.append({
                'servicio': servicio,
                'precio_original': servicio.price,
                'precio_final': precio_info['precio_final'],
                'descuento_aplicado': precio_info['descuento_aplicado'],
                'tiene_descuento': precio_info['tiene_descuento'],
                'porcentaje_descuento': precio_info['porcentaje_descuento'],
                'promocion': precio_info['promocion'],
                'promocion_nombre': precio_info['promocion_nombre'],
            })

        return resultado
