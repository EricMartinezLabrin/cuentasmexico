from django import template
try:
    from urllib.parse import urlencode
except ImportError:
    from urllib import urlencode

register = template.Library()

@register.simple_tag
def pagination_url(page_number, request):
    """
    Genera URL de paginación preservando los parámetros GET existentes
    """
    params = request.GET.copy()
    params['page'] = page_number
    return f"?{urlencode(params)}"

@register.simple_tag
def filter_pagination_url(page_number, filter_query=""):
    """
    Genera URL de paginación con filtros preservados
    """
    if filter_query:
        return f"?page={page_number}&{filter_query}"
    return f"?page={page_number}"
