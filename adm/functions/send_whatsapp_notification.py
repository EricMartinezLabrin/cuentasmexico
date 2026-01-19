import requests
from django.conf import settings


class Notification():
    def send_whatsapp_notification(message, lada, phone_number):
        """
        Send WhatsApp notification via Evolution API
        
        Args:
            message: Message text to send
            lada: Country code (e.g., 52 for Mexico)
            phone_number: Phone number without country code
            
        Returns:
            int: HTTP status code
        """
        try:
            # Get Evolution API configuration
            evo_api_url = settings.EVO_WHATSAPP_API_URL
            evo_instance = settings.EVO_INSTANCE
            evo_api_key = settings.EVO_API_KEY
            
            if not evo_api_url or not evo_instance or not evo_api_key:
                print("⚠️ WhatsApp API no configurada en .env")
                return 500
            
            # Prepare full phone number (Evolution API format: lada + phone)
            full_phone = f"{lada}{phone_number}"
            
            # Evolution API endpoint for sending text messages
            endpoint = f"{evo_api_url}/message/sendText/{evo_instance}"
            
            # Evolution API payload format
            payload = {
                "number": full_phone,
                "text": message
            }
            
            # Evolution API requires apikey in headers
            headers = {
                "apikey": evo_api_key,
                "Content-Type": "application/json"
            }
            
            response = requests.post(endpoint, json=payload, headers=headers, timeout=30)
            
            # Log response for debugging
            print(f"📱 WhatsApp API Response: {response.status_code}")
            if response.status_code not in [200, 201]:
                print(f"⚠️ Response body: {response.text}")
            
            return response.status_code
            
        except requests.exceptions.Timeout:
            print("⚠️ Timeout al enviar WhatsApp")
            return 408
        except requests.exceptions.RequestException as e:
            print(f"⚠️ Error al enviar WhatsApp: {str(e)}")
            return 500
        except Exception as e:
            print(f"⚠️ Error inesperado: {str(e)}")
            return 500