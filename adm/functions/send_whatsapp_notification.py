import requests
from django.conf import settings
from django.core.cache import cache
import re
import unicodedata


class Notification():
    @staticmethod
    def _safe_cache_key(value):
        raw = str(value or '').strip().lower()
        normalized = unicodedata.normalize('NFD', raw)
        normalized = ''.join(ch for ch in normalized if unicodedata.category(ch) != 'Mn')
        normalized = re.sub(r'[^a-z0-9_-]+', '_', normalized)
        normalized = re.sub(r'_+', '_', normalized).strip('_')
        return normalized or 'default'

    @staticmethod
    def _normalize_text(value):
        raw = str(value or '').strip().lower()
        normalized = unicodedata.normalize('NFD', raw)
        normalized = ''.join(ch for ch in normalized if unicodedata.category(ch) != 'Mn')
        return re.sub(r'\s+', ' ', normalized).strip()
    @staticmethod
    def _evo_config():
        evo_api_url = settings.EVO_WHATSAPP_API_URL
        evo_instance = settings.EVO_INSTANCE
        evo_api_key = settings.EVO_API_KEY
        if not evo_api_url or not evo_instance or not evo_api_key:
            return None
        return evo_api_url, evo_instance, evo_api_key

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
            config = Notification._evo_config()
            if not config:
                print("⚠️ WhatsApp API no configurada en .env")
                return 500
            evo_api_url, evo_instance, evo_api_key = config
            
            # Prepare full phone number (Evolution API format: lada + phone)
            full_phone = f"{lada}{phone_number}"
            
            endpoint = f"{evo_api_url}/message/sendText/{evo_instance}"
            payload = {"number": full_phone, "text": message}
            headers = {"apikey": evo_api_key, "Content-Type": "application/json"}
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

    @staticmethod
    def send_whatsapp_notification_with_media(message, lada, phone_number, media_url, mime_type='image/png', file_name='campana.png'):
        """
        Envía WhatsApp con imagen + caption usando Evolution /message/sendMedia.
        """
        try:
            config = Notification._evo_config()
            if not config:
                print("⚠️ WhatsApp API no configurada en .env")
                return 500
            evo_api_url, evo_instance, evo_api_key = config
            full_phone = f"{lada}{phone_number}"
            endpoint = f"{evo_api_url}/message/sendMedia/{evo_instance}"
            payload = {
                "number": full_phone,
                "mediatype": "image",
                "mimetype": mime_type,
                "caption": message or "",
                "media": str(media_url or "").strip(),
                "fileName": file_name,
            }
            headers = {"apikey": evo_api_key, "Content-Type": "application/json"}
            response = requests.post(endpoint, json=payload, headers=headers, timeout=30)
            print(f"🖼️ WhatsApp Media API Response: {response.status_code}")
            if response.status_code not in [200, 201]:
                print(f"⚠️ Media response body: {response.text}")
            return response.status_code
        except requests.exceptions.Timeout:
            print("⚠️ Timeout al enviar WhatsApp media")
            return 408
        except requests.exceptions.RequestException as e:
            print(f"⚠️ Error al enviar WhatsApp media: {str(e)}")
            return 500

    def send_whatsapp_group_notification(message, group_id):
        """
        Send WhatsApp notification to a group via Evolution API.

        Args:
            message: Message text to send
            group_id: WhatsApp group id (example: 1203630...@g.us)
        """
        try:
            config = Notification._evo_config()
            if not config:
                print("⚠️ WhatsApp API no configurada en .env")
                return 500
            evo_api_url, evo_instance, evo_api_key = config

            endpoint = f"{evo_api_url}/message/sendText/{evo_instance}"
            payload = {"number": str(group_id).strip(), "text": message}
            headers = {"apikey": evo_api_key, "Content-Type": "application/json"}
            response = requests.post(endpoint, json=payload, headers=headers, timeout=30)
            print(f"📣 WhatsApp Group API Response: {response.status_code}")
            if response.status_code not in [200, 201]:
                print(f"⚠️ Group response body: {response.text}")
            return response.status_code
        except Exception as e:
            print(f"⚠️ Error enviando WhatsApp a grupo: {str(e)}")
            return 500

    @staticmethod
    def send_whatsapp_group_notification_with_media(message, group_id, media_url, mime_type='image/png', file_name='campana.png'):
        try:
            config = Notification._evo_config()
            if not config:
                print("⚠️ WhatsApp API no configurada en .env")
                return 500
            evo_api_url, evo_instance, evo_api_key = config
            endpoint = f"{evo_api_url}/message/sendMedia/{evo_instance}"
            payload = {
                "number": str(group_id).strip(),
                "mediatype": "image",
                "mimetype": mime_type,
                "caption": message or "",
                "media": str(media_url or "").strip(),
                "fileName": file_name,
            }
            headers = {"apikey": evo_api_key, "Content-Type": "application/json"}
            response = requests.post(endpoint, json=payload, headers=headers, timeout=30)
            print(f"🖼️ WhatsApp Group Media API Response: {response.status_code}")
            if response.status_code not in [200, 201]:
                print(f"⚠️ Group media response body: {response.text}")
            return response.status_code
        except Exception as e:
            print(f"⚠️ Error enviando WhatsApp media a grupo: {str(e)}")
            return 500

    def fetch_whatsapp_groups():
        """
        Fetch available WhatsApp groups from Evolution API.

        Returns:
            list[dict]: [{'id': '1203...@g.us', 'name': 'Grupo'}]
        """
        try:
            config = Notification._evo_config()
            if not config:
                return []
            evo_api_url, evo_instance, evo_api_key = config

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

    @staticmethod
    def find_label_id_by_name(label_name):
        try:
            safe_label = Notification._safe_cache_key(label_name)
            cache_key = f"evo_label_id::{safe_label}"
            cached = cache.get(cache_key)
            if cached:
                return cached
            config = Notification._evo_config()
            if not config:
                return None
            evo_api_url, evo_instance, evo_api_key = config
            endpoint = f"{evo_api_url}/label/findLabels/{evo_instance}"
            headers = {"apikey": evo_api_key, "Content-Type": "application/json"}
            response = requests.get(endpoint, headers=headers, timeout=20)
            if response.status_code not in [200, 201]:
                return None
            data = response.json()
            labels = []
            if isinstance(data, list):
                labels = data
            elif isinstance(data, dict):
                for key in ("labels", "data", "result", "items"):
                    value = data.get(key)
                    if isinstance(value, list):
                        labels = value
                        break
            target = Notification._normalize_text(label_name)
            for item in labels:
                if not isinstance(item, dict):
                    continue
                current_name = Notification._normalize_text(item.get('name') or item.get('label') or '')
                if current_name == target:
                    found_id = str(item.get('id') or item.get('labelId') or '').strip() or None
                    if found_id:
                        cache.set(cache_key, found_id, 600)
                    return found_id
            return None
        except Exception:
            return None

    @staticmethod
    def handle_label(number, label_id, action='add'):
        try:
            config = Notification._evo_config()
            if not config:
                return False
            evo_api_url, evo_instance, evo_api_key = config
            endpoint = f"{evo_api_url}/label/handleLabel/{evo_instance}"
            headers = {"apikey": evo_api_key, "Content-Type": "application/json"}
            payload = {
                "number": str(number).strip(),
                "labelId": str(label_id).strip(),
                "action": "remove" if str(action).lower() == "remove" else "add",
            }
            response = requests.post(endpoint, json=payload, headers=headers, timeout=20)
            return response.status_code in [200, 201]
        except Exception:
            return False

    @staticmethod
    def set_contact_label_by_name(lada, phone_number, label_name, enabled=True):
        full_phone = f"{lada}{phone_number}"
        label_id = Notification.find_label_id_by_name(label_name)
        if not label_id:
            print(f"⚠️ Label no encontrada en Evolution: {label_name}")
            return False
        action = 'add' if enabled else 'remove'
        candidates = [
            str(full_phone).strip(),
            f"+{str(full_phone).strip()}",
            f"{str(full_phone).strip()}@s.whatsapp.net",
        ]
        for candidate in candidates:
            if Notification.handle_label(candidate, label_id, action=action):
                return True
        print(f"⚠️ No se pudo {'agregar' if enabled else 'quitar'} label {label_name} a {full_phone}")
        return False
