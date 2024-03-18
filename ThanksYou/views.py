
from django.http import HttpResponse
from django.shortcuts import render

from adm.models import Sale

# Create your views here.
def index(request,price,event_id):
    """
    Main Admin Page
    """
    template_name = 'ThanksYou/index.html'
    try:
        sale = Sale.objects.get(id=event_id)
        if sale.payment_amount != price:
            return HttpResponse('<h1>Página no existe</h1> <p>Verifique la URL</p>')
    except:
        return HttpResponse('<h1>Página no existe</h1> <p>Verifique la URL</p>')
    return render(request, template_name, {
        "price":price,
        "event_id":event_id,
    })
