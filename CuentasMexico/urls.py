
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.static import serve
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

# Local
from . import views

# Health check view
def health_check(request):
    """Health check endpoint para Dokploy/Docker"""
    return JsonResponse({'status': 'ok', 'message': 'Aplicación corriendo'})

urlpatterns = [
    path('health/', health_check, name='health_check'),
    path('', include('index.urls')),
    path('admin/', admin.site.urls),
    path('adm/', include('adm.urls')),
    path('api/', include('api.urls')),
    path('api_bot/', include('api_bot.urls')),
    path('ThanksYou/', include('ThanksYou.urls')),
]

urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve, {
            'document_root': settings.MEDIA_ROOT
            })
]
