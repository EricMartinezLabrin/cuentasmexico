from django import template
from django.conf import settings

register = template.Library()


@register.simple_tag
def media_url(file_field):
    """
    Template tag para generar URL de media correctamente.
    Funciona con archivos locales y Backblaze B2.
    
    Uso:
        {% load media_tags %}
        {% media_url objeto.logo %}
    """
    if not file_field:
        return ''
    
    try:
        # Si es un FileField de Django, usar .url
        if hasattr(file_field, 'url'):
            url = file_field.url
            # Si la URL ya es completa (https://...), retornarla
            if url and url.startswith('http'):
                return url
            return url
        
        # Si es un string
        file_str = str(file_field)
        
        # Si ya es una URL completa
        if file_str.startswith('http'):
            return file_str
        
        # Si es una ruta de Backblaze (sin /media/)
        if hasattr(settings, 'BACKBLAZE_BUCKET_URL') and settings.BACKBLAZE_BUCKET_URL:
            # Verificar si parece ser una ruta de Backblaze (tiene formato folder/timestamp_filename)
            if '/' in file_str and not file_str.startswith('/'):
                parts = file_str.split('/')
                if len(parts) >= 2 and parts[0] in ['business', 'services', 'bank', 'users', 'files']:
                    return f"{settings.BACKBLAZE_BUCKET_URL}/{file_str}"
        
        # Fallback: ruta local con /media/
        if not file_str.startswith('/'):
            return f"/media/{file_str}"
        
        return file_str
    
    except Exception:
        return ''


@register.filter
def smart_media(file_field):
    """
    Filtro para usar en templates como: {{ objeto.logo|smart_media }}
    """
    return media_url(file_field)
