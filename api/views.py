from django.forms import model_to_dict
from django.shortcuts import render
from django.contrib.auth import authenticate
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User

import json

from adm.models import Business, Sale, UserDetail
from .functions.notifications import send_push_notification


#POST
@csrf_exempt
def checkFlowPaymentByTokenApi(request):
    url = "https://sandbox.flow.cl/api"
    route = "/payment/getStatusExtended"
    apiKey = flow_api_key
    secretKey = flow_secret_key
    sandbox = Business2.objects.get(id=1).stripe_sandbox
    if request.method == 'POST':
        token = request.POST.get('token')
        if token:
            api = FlowAPI(flow_key=apiKey, flow_secret=secretKey,flow_use_sandbox=sandbox)
            parametros = {"apiKey": api.apiKey, "token": token}
            # status = api.objetos.call_get_payment_getstatus(
            #     parameters=genera_parametros(parametros, api.secretKey)
            # )
            status = requests.get(url+route, params=genera_parametros(parametros, api.secretKey))
            status_decode = status.json()
            if status_decode["status"] == 2 or status_decode["status"] == "2":
                expiration_long = int(status_decode["optional"]["expiration"])
                expiration_date = timezone.now() + relativedelta(months=expiration_long)
                sale = SalesApi.SalesCreateApi(request,status_decode["payer"],status_decode["optional"]["serviceId"],expiration_date,"flow",status_decode["amount"],status_decode["flowOrder"])
                return JsonResponse(status=200, data={"status": "success", "message": "Pago realizado con exito"})
            else:
                return JsonResponse(status=400, data={"status": "error", "message": "Pago no realizado"})
        else:
            return JsonResponse(status=400, data={"status": "error", "message": "Token no enviado"})
    else:
        return JsonResponse(status=400, data={"status": "error", "message": "Metodo no permitido"})

@csrf_exempt
def saleApi(request):
    if request.method == 'POST':
        data = json.loads(request.body.decode('utf-8'))
        expiration_long = data['expiration_long']
        expiration_date = timezone.now() + relativedelta(months=expiration_long)
        customer_email = data['customer_email']
        service_id = data['service_id']
        platform = data['platform']
        amount = data['amount']
        order_id = data['order_id']
        sale = SalesApi.SalesCreateApi(request,customer_email,service_id,expiration_date,platform,amount,order_id)

        if sale == False:
            return JsonResponse(status=400, data={"status": "error", "message": "Hubo un error al crear la cuenta, contacta a soporte"})
        else:
            return JsonResponse(status=200, data={"status": "success", "message": "Cuenta Creada con Exito"})

@csrf_exempt    
def stripe_create_payment(request):
    if request.method == "POST":
        # Decodifica la información en formato JSON a un diccionario Python
        data = json.loads(request.body.decode('utf-8'))
        currency = data.get("currency")
        amount = data.get("amount")

    # Crear el pago en Stripe
    payment_intent = stripe.PaymentIntent.create(
        amount=amount,
        currency=currency,
        automatic_payment_methods={
            'enabled': True,
        },
    )
    # Retornar el client secret generado por Stripe
    return JsonResponse({
        "clientSecret": payment_intent.client_secret
    })

@csrf_exempt
def setToken(request):
    # verificamos si el método HTTP es POST
    if request.method == "POST":
        # obtenemos los datos enviados en el cuerpo de la petición y los convertimos en un diccionario python
        data = json.loads(request.body)
        # obtenemos el valor del campo 'username' del diccionario
        username = data.get('username')
        # obtenemos el valor del campo 'token' del diccionario
        token = data.get('token')

        try:
            # obtenemos un objeto User con el nombre de usuario obtenido
            user = User.objects.get(username=username)
            # obtenemos un objeto UserDetail asociado al objeto User obtenido
            user_detail = UserDetail.objects.get(user=user)

            # comparamos el token almacenado en el objeto UserDetail con el token recibido en la petición
            if user_detail.token != token or user_detail.token is None or user_detail.token == "":
                # si los tokens son diferentes o el token almacenado es None o una cadena vacía,
                # actualizamos el token almacenado en el objeto UserDetail y guardamos los cambios
                user_detail.token = token
                user_detail.save()
                # devolvemos una respuesta HTTP con un código de estado 200 y un diccionario json con el mensaje 'token updated'
                return JsonResponse(status=200, data={'detail': 'token updated'})
            else:
                # si los tokens son iguales, devolvemos una respuesta HTTP con un código de estado 200 y un diccionario json con el mensaje 'token already updated'
                return JsonResponse(status=200, data={'detail': 'token already updated'})

        except User.DoesNotExist:
            # si no encontramos un objeto User con el nombre de usuario obtenido,
            # devolvemos una respuesta HTTP con un código de estado 400 y un diccionario json con el mensaje 'user does not exist'
            return JsonResponse(status=400, data={'detail': 'user does not exist'})

        except UserDetail.DoesNotExist:
            # si no encontramos un objeto UserDetail asociado al objeto User obtenido,
            # creamos uno nuevo con los datos especificados y guardamos los cambios
            UserDetail.objects.create(
                business=Business.objects.get(id=1),
                user=user,
                phone_number="0000000000",
                lada=0,
                country="México",
                token=token
            )
            # devolvemos una respuesta HTTP con un código de estado 200 y un diccionario json con el mensaje 'token updated'
            return JsonResponse(status=200, data={'detail': 'token updated'})

    else:
        # si el método HTTP no es POST, devolvemos una respuesta HTTP con un código de estado 405 y un diccionario json con el mensaje 'method not allowed'
        return JsonResponse(status=405, data={'detail': 'method not allowed'})


@csrf_exempt
# Definir función de envío de notificaciones HTTP con request
def sendNotification(request):
    # Comprobar si el método de solicitud es POST
    if request.method == 'POST':
        # Cargar los datos de clientes en JSON desde el cuerpo del request
        customers = json.loads(request.body)
        # Crear lista vacía para almacenar las respuestas
        response = []
        # Recorrer cada uno de los clientes
        for customer in customers:
            print(customer)
            # Guardar el token del cliente
            token = customer["token"]
            # Guardar el título de la notificación del cliente
            title = customer["title"]
            # Guardar el cuerpo del mensaje
            body = customer["body"]
            # Guardar los datos adicionales necesarios
            url = customer["url"]

            if customer["data"]:
                data = customer["data"]
            else:
                data = {}

            # Enviar notificación push HTTP al cliente
            request = send_push_notification(token, title, body, url, data)
            # Agregar la respuesta a la lista de respuestas
            response.append(request)
        # Devolver una respuesta de éxito con los detalles y respuestas
        return JsonResponse(status=200, data={'detail': "Notifications sent successfully", "response": response})
    # Si el método de solicitud no es POST, devolver un error "Método no permitido"
    else:
        return JsonResponse(status=405, data={'detail': 'method not allowed'})

@csrf_exempt
def create_user_api(request):
    if request.method == "POST":
        data = json.loads(request.body)
        username = data.get('username')
        password = data.get('password')
        email = data.get('email')
        user = User.objects.create_user(username=username, password=password, email=email)
        user.save()
        return JsonResponse(status=200, data={'detail': 'user created'})
    else:
        return JsonResponse(status=405, data={'detail': 'method not allowed'})

#GET
def getServices(request):
    if request.is_secure():
        protocol = 'https://'
    else:
        protocol = 'http://'
    
    host = '192.168.100.12:8000/media/' ##request.get_host()
    if request.method == 'GET':
        services = Service.objects.filter(is_active=True, countable=True).values(
            "id", "name", "image", "description", "price")
        for service in services:
            service["image"] = protocol + host + str(service["image"])
        return JsonResponse(status=200, data={'detail': list(services)})
    else:
        return JsonResponse(status=405, data={'detail': 'method not allowed'})
    
def loginApi(request, username, password):
    """
    El siguiente código es una función llamada loginApi que recibe tres parámetros request, username y password. 
    La función se encarga de autenticar al usuario y, si la autenticación es correcta, retorna un objeto JSON con la 
    información del usuario y algunos detalles adicionales. 
    """
    # autenticamos al usuario con las credenciales proporcionadas
    user = authenticate(username=username, password=password)

    # si el usuario es autenticado correctamente
    if user is not None:
        # Creamos un diccionario user_dict con algunos detalles del usuario
        user_dict = {"username": user.username, "first_name": user.first_name,
                     "last_name": user.last_name, "email": user.email}

        # Obtenemos los detalles adicionales del usuario y los agregamos a una lista
        user_detail = list(UserDetail.objects.filter(user=user.id).values(
            "phone_number", "lada", "country", "free_days"))

        # retornamos un objeto JsonResponse con los detalles del usuario autenticado
        return JsonResponse(status=200, data={'user': user_dict, 'detail': user_detail})

    # si la autenticación es inválida
    else:
        # retornamos un objeto JsonResponse con un mensaje de error
        return JsonResponse(status=400, data={'detail': 'invalid username or password'})

def getActiveAccounts(request):
    """
    El siguiente código busca obtener cuentas activas de un usuario autenticado mediante una solicitud (request) de tipo GET.
    """
    if request.method == 'GET':  # Verificar si la solicitud es GET
        # Obtener los datos de autorización de la solicitud
        data = json.loads(request.headers['Authorization'])
        # Obtener el nombre de usuario del objeto de datos de autorización
        username = data.get('username')
        # Obtener la contraseña del objeto de datos de autorización
        password = data.get('password')
        # Autenticar el username y la contraseña con authenticate()
        auth = authenticate(username=username, password=password)
        if auth is not None:  # Verificar si la autenticación tuvo éxito
            # Obtener las ventas asociadas a la cuenta autenticada y las informaciónes de las cuentas
            sales = Sale.objects.filter(status=True, customer=auth).values("account__account_name__description", "account__account_name__logo",
                                                                           "account__email", "account__password", "account__pin", "account__profile", "expiration_date")
            # Devolver las ventas de la cuenta autenticada
            return JsonResponse(status=200, data={'detail': list(sales)})
        else:
            # Devolver un error si la autenticación no fue exitosa
            return JsonResponse(status=400, data={'detail': 'invalid username or password'})
    else:
        # Devolver un error si la solicitud no fue GET
        return JsonResponse(status=405, data={'detail': 'method not allowed'})

def get_keys(request):
    if request.method=="GET":
        try:
            keys = Business2.objects.get(id=1)
        except Business2.DoesNotExist:
            return JsonResponse(status=400, data={"status": "error", "message": "No se encontraron las llaves"})
        return JsonResponse(status=200, data={"status": "success", "message": "Llaves encontradas", "data": {"stripe_api_key": keys.stripe_customer_key, "flow_api_key": keys.flow_customer_key, "flow_secret_key": keys.flow_secret_key,"flow_show":keys.flow_show,"stripe_sandbox":keys.stripe_sandbox}})      

def get_services_by_name_api(request, name):
    if request.is_secure():
        protocol = 'https://'
    else:
        protocol = 'http://'
    
    host = '192.168.100.12:8000/media/' ##request.get_host()
    if request.method == 'GET':
        services = Service.objects.filter(name__icontains=name, is_active=True, countable=True).values(
            "id", "name", "image", "description", "price")
        for service in services:
            service["image"] = protocol + host + str(service["image"])
        return JsonResponse(status=200, data={'detail': list(services)})
    else:
        return JsonResponse(status=405, data={'detail': 'method not allowed'})



