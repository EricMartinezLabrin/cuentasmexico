import requests


class Notification():
    def send_whatsapp_notification(message, lada, phone_number):
        # Send WhatsApp notification
            if lada == 52:
                customer_phone = f'{lada}1{phone_number}'
            else:
                customer_phone = f'{lada}9{phone_number}'
            result = requests.post('https://hook.us1.make.com/tjbu4dtlfb3uilc1111xt3o6lha7jlbv', {
                'phone': customer_phone,
                'body': message
            })
            return result.status_code