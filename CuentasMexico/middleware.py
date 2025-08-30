from django.contrib.sessions.models import Session
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse
from django.conf import settings


class RemoveXFrameOptionsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if 'X-Frame-Options' in response.headers:
            del response.headers['X-Frame-Options']
        return response


class SingleSessionMiddleware:
    """
    Middleware que permite controlar sesiones concurrentes
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Permitir múltiples sesiones por defecto
        # Solo procesar si el usuario está autenticado
        if request.user.is_authenticated:
            # Obtener la sesión actual
            current_session_key = request.session.session_key
            
            # Si queremos limitar a una sola sesión por usuario, descomenta el siguiente código:
            # self.limit_single_session(request, current_session_key)
            
        response = self.get_response(request)
        return response

    def limit_single_session(self, request, current_session_key):
        """
        Método para limitar a una sola sesión por usuario
        """
        # Buscar otras sesiones del mismo usuario
        user_sessions = Session.objects.filter(
            expire_date__gte=timezone.now()
        )
        
        for session in user_sessions:
            session_data = session.get_decoded()
            if (session_data.get('_auth_user_id') == str(request.user.id) and 
                session.session_key != current_session_key):
                # Eliminar sesiones anteriores del mismo usuario
                session.delete()
