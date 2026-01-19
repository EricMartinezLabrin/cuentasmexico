"""
Context processors para la app index.
"""
from adm.models import Affiliate


def affiliate_context(request):
    """
    Agrega informacion de afiliado al contexto de templates.
    """
    context = {
        'user_is_affiliate': False,
        'user_affiliate': None,
    }

    if request.user.is_authenticated:
        try:
            affiliate = request.user.affiliate
            if affiliate.status == 'activo':
                context['user_is_affiliate'] = True
                context['user_affiliate'] = affiliate
        except Affiliate.DoesNotExist:
            pass

    return context
