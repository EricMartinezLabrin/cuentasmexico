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

    def send_whatsapp_group_notification(message, group_id):
        """
        Send WhatsApp notification to a group via Evolution API.

        Args:
            message: Message text to send
            group_id: WhatsApp group id (example: 1203630...@g.us)
        """
        try:
            evo_api_url = settings.EVO_WHATSAPP_API_URL
            evo_instance = settings.EVO_INSTANCE
            evo_api_key = settings.EVO_API_KEY

            if not evo_api_url or not evo_instance or not evo_api_key:
                print("⚠️ WhatsApp API no configurada en .env")
                return 500

            endpoint = f"{evo_api_url}/message/sendText/{evo_instance}"
            payload = {
                "number": str(group_id).strip(),
                "text": message,
            }
            headers = {
                "apikey": evo_api_key,
                "Content-Type": "application/json",
            }
            response = requests.post(endpoint, json=payload, headers=headers, timeout=30)
            print(f"📣 WhatsApp Group API Response: {response.status_code}")
            if response.status_code not in [200, 201]:
                print(f"⚠️ Group response body: {response.text}")
            return response.status_code
        except Exception as e:
            print(f"⚠️ Error enviando WhatsApp a grupo: {str(e)}")
            return 500

    def fetch_whatsapp_groups():
        """
        Fetch available WhatsApp groups from Evolution API.

        Returns:
            list[dict]: [{'id': '1203...@g.us', 'name': 'Grupo'}]
        """
        try:
            evo_api_url = settings.EVO_WHATSAPP_API_URL
            evo_instance = settings.EVO_INSTANCE
            evo_api_key = settings.EVO_API_KEY
            if not evo_api_url or not evo_instance or not evo_api_key:
                return []

            endpoint = f"{evo_api_url}/group/fetchAllGroups/{evo_instance}?getParticipants=false"
            headers = {"apikey": evo_api_key, "Content-Type": "application/json"}
            response = requests.get(endpoint, headers=headers, timeout=30)
            if response.status_code not in [200, 201]:
                print(f"⚠️ Error obteniendo grupos Evolution API: {response.status_code} {response.text}")
                return []

            data = response.json()
            groups_raw = []
            if isinstance(data, list):
                groups_raw = data
            elif isinstance(data, dict):
                for key in ("groups", "data", "result", "items"):
                    value = data.get(key)
                    if isinstance(value, list):
                        groups_raw = value
                        break
                if not groups_raw and isinstance(data.get("group"), list):
                    groups_raw = data.get("group")

            groups = []
            for g in groups_raw:
                if not isinstance(g, dict):
                    continue
                gid = (
                    g.get("id")
                    or g.get("jid")
                    or g.get("groupJid")
                    or g.get("remoteJid")
                    or ""
                )
                name = (
                    g.get("subject")
                    or g.get("name")
                    or g.get("groupName")
                    or gid
                )
                gid = str(gid).strip()
                name = str(name).strip()
                if not gid:
                    continue
                groups.append({"id": gid, "name": name or gid})
            return groups
        except Exception as e:
            print(f"⚠️ Error obteniendo grupos WhatsApp: {str(e)}")
            return []
        except Exception as e:
            print(f"⚠️ Error inesperado: {str(e)}")
            return 500
