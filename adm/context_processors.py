"""
Context processors para la aplicación adm
"""
from adm.functions.promociones import PromocionManager


def promociones_banners(request):
    """
    Agrega las promociones activas con banners a todas las vistas
    """
    return {
        'promociones_banner': PromocionManager.obtener_promociones_banner()
    }
