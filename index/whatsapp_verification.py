"""
WhatsApp verification module for user registration
"""
import requests
import random
import string
from django.conf import settings
from django.core.cache import cache
from adm.functions.country import Country


class WhatsAppVerification:
    """Handle WhatsApp verification codes"""

    @staticmethod
    def generate_verification_code(length=6):
        """Generate a random 6-digit verification code"""
        return ''.join(random.choices(string.digits, k=length))

    @staticmethod
    def get_lada_from_country(country_name):
        """Get country code (lada) from country name"""
        countries_dict = Country.get_country_lada()
        return countries_dict.get(country_name, '')

    @staticmethod
    def send_verification_code(phone_number, country, code, full_number_override=None):
        """
        Send verification code via Evolution API WhatsApp

        Args:
            phone_number: Phone number without country code (db format - últimos 8 dígitos para Chile)
            country: Country name (e.g., 'México', 'Chile')
            code: 6-digit verification code
            full_number_override: Optional - número completo con código país (ej: 56912345678)
                                  Si se proporciona, se usa este en lugar de lada+phone_number

        Returns:
            dict: {'success': bool, 'message': str}
        """
        try:
            # Determine full phone number for WhatsApp API
            if full_number_override:
                # Usar el número completo proporcionado (ya normalizado)
                full_phone = full_number_override
            else:
                # Comportamiento original: concatenar lada + phone_number
                lada = WhatsAppVerification.get_lada_from_country(country)
                if not lada:
                    return {'success': False, 'message': 'País no válido'}
                full_phone = f"{lada}{phone_number}"

            # Prepare message
            message = f"Tu código de verificación para Cuentas México es: {code}\n\nEste código expira en 10 minutos."

            # Get Evolution API configuration
            evo_api_url = settings.EVO_WHATSAPP_API_URL
            evo_instance = settings.EVO_INSTANCE
            evo_api_key = settings.EVO_API_KEY

            if not evo_api_url or not evo_instance or not evo_api_key:
                return {'success': False, 'message': 'WhatsApp API no configurada'}

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

            response = requests.post(endpoint, json=payload, headers=headers, timeout=10)

            if response.status_code == 200 or response.status_code == 201:
                # Store code in cache with 10 minute expiration
                # IMPORTANTE: usar phone_number (db format) para el cache key
                cache_key = f"whatsapp_verify_{country}_{phone_number}"
                cache.set(cache_key, code, timeout=600)  # 10 minutes

                return {'success': True, 'message': 'Código enviado correctamente'}
            else:
                return {'success': False, 'message': f'Error al enviar mensaje: {response.status_code}'}

        except requests.exceptions.Timeout:
            return {'success': False, 'message': 'Tiempo de espera agotado al enviar mensaje'}
        except requests.exceptions.RequestException as e:
            return {'success': False, 'message': f'Error de conexión: {str(e)}'}
        except Exception as e:
            return {'success': False, 'message': f'Error inesperado: {str(e)}'}

    @staticmethod
    def verify_code(phone_number, country, code):
        """
        Verify if the provided code matches the one sent

        Args:
            phone_number: Phone number without country code
            country: Country name
            code: Code to verify

        Returns:
            dict: {'success': bool, 'message': str}
        """
        cache_key = f"whatsapp_verify_{country}_{phone_number}"
        stored_code = cache.get(cache_key)

        if not stored_code:
            return {'success': False, 'message': 'Código expirado o no encontrado. Solicita uno nuevo.'}

        if stored_code == code:
            # Mark as verified in cache
            verified_key = f"whatsapp_verified_{country}_{phone_number}"
            cache.set(verified_key, True, timeout=3600)  # 1 hour to complete registration

            # Delete verification code
            cache.delete(cache_key)

            return {'success': True, 'message': 'Teléfono verificado correctamente'}
        else:
            return {'success': False, 'message': 'Código incorrecto'}

    @staticmethod
    def is_verified(phone_number, country):
        """
        Check if a phone number has been verified

        Args:
            phone_number: Phone number without country code
            country: Country name

        Returns:
            bool: True if verified, False otherwise
        """
        verified_key = f"whatsapp_verified_{country}_{phone_number}"
        return cache.get(verified_key, False)
