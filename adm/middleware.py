from django.utils.deprecation import MiddlewareMixin
from adm.models import PageVisit


class PageVisitMiddleware(MiddlewareMixin):
    """
    Middleware para rastrear visitas de páginas automáticamente
    """

    def process_request(self, request):
        """
        Captura información de cada request y la guarda en la base de datos
        SOLO para páginas públicas del sitio web
        """
        path = request.path

        # Ignorar todas las rutas privadas/internas
        # Solo rastrear páginas públicas del sitio web
        ignored_prefixes = [
            '/adm/',           # Panel de administración
            '/admin/',         # Django admin
            '/static/',        # Archivos estáticos
            '/media/',         # Archivos multimedia
            '/api/',           # API endpoints
            '/api_bot/',       # API bot
            '/login',          # Login
            '/logout',         # Logout
            '/accounts/',      # Cuentas de Django
        ]

        if any(path.startswith(prefix) for prefix in ignored_prefixes):
            return None

        # Determinar qué página pública es
        page_type = 'other'
        if path == '/' or path == '':
            page_type = 'home'
        elif 'myaccount' in path.lower() or 'mi-cuenta' in path.lower():
            page_type = 'myaccount'
        elif 'cart' in path.lower() or 'carrito' in path.lower():
            page_type = 'cart'
        elif 'checkout' in path.lower() or 'pago' in path.lower():
            page_type = 'checkout'
        elif 'services' in path.lower() or 'servicios' in path.lower():
            page_type = 'services'

        # Obtener información del request
        user = request.user if request.user.is_authenticated else None
        ip_address = self.get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        referrer = request.META.get('HTTP_REFERER', '')
        session_key = request.session.session_key

        # Crear el registro de visita solo para páginas públicas
        try:
            PageVisit.objects.create(
                page=page_type,
                page_url=path,
                user=user,
                ip_address=ip_address,
                user_agent=user_agent[:500] if user_agent else '',
                referrer=referrer[:500] if referrer else '',
                session_key=session_key
            )
        except Exception as e:
            # No fallar si hay error al guardar la visita
            pass

        return None

    def get_client_ip(self, request):
        """
        Obtener la IP real del cliente
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
