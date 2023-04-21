from django.forms import model_to_dict
from django.shortcuts import render
from django.contrib.auth import authenticate
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

import json

from adm.models import Sale, UserDetail

@csrf_exempt
def loginApi(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        username = data.get('username')
        password = data.get('password')
        user = authenticate(username=username, password=password)
        if user is not None:
            user_dict = {"username":user.username, "first_name":user.first_name, "last_name":user.last_name, "email":user.email}
            user_detail = list(UserDetail.objects.filter(user=user.id).values("phone_number","lada","country","free_days"))
            return JsonResponse(status=200, data={'user':user_dict, 'detail':user_detail})
        else:
            return JsonResponse(status=400, data={'detail':'invalid username or password'})
    else:
        return JsonResponse(status=405, data={'detail':'method not allowed'})

@csrf_exempt
def getActiveAccounts(request):
    if request.method == 'GET':
        data = json.loads(request.headers['Authorization'])
        username = data.get('username')
        password = data.get('password')
        auth = authenticate(username=username, password=password)
        if auth is not None:
            sales = Sale.objects.filter(status=True,customer=auth).values("account__account_name__description","account__account_name__logo","account__email","account__password","account__pin","account__profile","expiration_date")
            return JsonResponse(status=200, data={'detail':list(sales)})
        else:
            return JsonResponse(status=400, data={'detail':'invalid username or password'})
    else:
        return JsonResponse(status=405, data={'detail':'method not allowed'})