"""
Template tags personalizados para trabajar con promociones
"""
from django import template
from adm.functions.promociones import PromocionManager

register = template.Library()


@register.simple_tag
def calcular_precio_promocion(servicio, cantidad=1):
    """
    Calcula y retorna el precio con descuento aplicado

    Uso en template:
        {% calcular_precio_promocion servicio %}
        {% calcular_precio_promocion servicio 2 %}
    """
    resultado = PromocionManager.calcular_precio_con_descuento(servicio, cantidad)
    return resultado['precio_final']


@register.simple_tag
def obtener_info_promocion(servicio, cantidad=1):
    """
    Retorna toda la información de precio y promoción

    Uso en template:
        {% obtener_info_promocion servicio as precio_info %}
        {{ precio_info.precio_final }}
        {{ precio_info.tiene_descuento }}
        {{ precio_info.promocion_nombre }}
    """
    return PromocionManager.calcular_precio_con_descuento(servicio, cantidad)


@register.filter
def tiene_promocion(servicio):
    """
    Verifica si un servicio tiene promoción activa

    Uso en template:
        {% if servicio|tiene_promocion %}
            ¡En promoción!
        {% endif %}
    """
    promocion = PromocionManager.obtener_promocion_activa(servicio)
    return promocion is not None and promocion.is_active()


@register.inclusion_tag('adm/components/precio_promocion.html')
def mostrar_precio_promocion(servicio, cantidad=1, mostrar_original=True):
    """
    Muestra el precio con formato y promoción aplicada

    Uso en template:
        {% mostrar_precio_promocion servicio %}
        {% mostrar_precio_promocion servicio 2 %}
        {% mostrar_precio_promocion servicio mostrar_original=False %}
    """
    precio_info = PromocionManager.calcular_precio_con_descuento(servicio, cantidad)

    return {
        'servicio': servicio,
        'precio_original': precio_info['precio_original'],
        'precio_final': precio_info['precio_final'],
        'tiene_descuento': precio_info['tiene_descuento'],
        'descuento_aplicado': precio_info['descuento_aplicado'],
        'porcentaje_descuento': precio_info['porcentaje_descuento'],
        'promocion': precio_info['promocion'],
        'mostrar_original': mostrar_original,
    }
