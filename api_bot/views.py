import json
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
import requests
from django.views.decorators.csrf import csrf_exempt

local_url = 'https://cuentasmexico.mx/api'
pyc_url = 'https://bdpyc.cl/api'

# Create your views here.
@csrf_exempt
def get_active_sales_by_user_api(request,customer):
    if request.method == 'GET':
        #get customer data using requests to the API get_active_sales_by_user_api
        # Make a GET request to the API endpoint
        response = requests.get(f'{local_url}/get_active_sales_by_user_api/{customer}',verify=False)
        # Check if the request was successful
        if response.status_code == 200:
            # Extract the customer data from the response
            customer_data = response.json()
            if '@premiumycodigos.cl' in customer_data:
                print('El usuario es premium')

            account_list = ""
            account_lenght = len(customer_data['detail'])
            for account in customer_data['detail']:
                if '@premiumycodigos.cl' in account['account_id__email'] or '@berberdna.tn' in account['account_id__email']:
                    pyc_response = requests.get(f'{pyc_url}/get_password_by_email_api?email={account["account_id__email"]}',verify=False)
                    if pyc_response.status_code == 200:
                        pyc_data = pyc_response.json()
                        account['account_id__password'] = pyc_data['password']

                if 'Netflix Emergencias' in account['account_id__account_name__description']:
                    account['account_id__account_name__description'] = 'Netflix'

                account_list += f"*{account['account_id__account_name__description']}*:\n"
                account_list += f"*Email:* {account['account_id__email']}\n"
                account_list += f"*Password:* {account['account_id__password']}\n"
                account_list += f"*Pin:* {account['pin_status']}\n"
                account_list += f"*Perfil:* {account['account_id__profile']}\n\n"
                account_list += f"*Vencimiento:{account['expiration_date']}\n\n"
                
            
            json_to_bot ={
                "accounts":account_lenght,
                "response":account_list
            }
            return JsonResponse(status=200, data={'detail': json_to_bot})
        else:
            return JsonResponse({"error": "Failed to retrieve customer data"}, status=response.status_code)
    else:
        return JsonResponse({"error": "Invalid request method"}, status=400)
    

# POSt
@csrf_exempt
def bot_gpt_history_api(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        history = data['custom_fields']['Historial del Chat']
        webhook = data['custom_fields']['WebHook']
        chatgpt = data['custom_fields']['ChatGpt']
        user_response = data['custom_fields']['Respuesta del Usuario']

        if history:
            if webhook:
                if webhook not in history:
                    history+=f"\n{webhook}"
            if chatgpt:
                if chatgpt not in history:
                    history+=f"\n{chatgpt}"
            if user_response:
                if user_response not in history:
                    history+=f"\n{user_response}"
        else:
            history = ""
            if webhook:
                history+=f"\n{webhook}"
            if chatgpt:
                history+=f"\n{chatgpt}"
            if user_response:
                history+=f"\n{user_response}"

    
        return JsonResponse(status=200, data={'detail': history})
    else:
        return JsonResponse({"error": "Invalid request method"}, status=400)