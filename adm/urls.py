#django
from django.urls import path
from django.contrib.auth.decorators import login_required


from . import views


urlpatterns = [
    #extension: /adm/
    path('',views.index,name='index')
]