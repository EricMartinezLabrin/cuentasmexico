
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.static import serve
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth.decorators import login_required

# Local
from . import views

urlpatterns = [
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
