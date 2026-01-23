"""
Utilidades para el manejo de números telefónicos
"""


class PhoneNumberHandler:
    """Clase para normalizar y manejar números telefónicos según el país"""

    @staticmethod
    def normalize_chile_phone(phone_number):
        """
        Normaliza un número telefónico chileno.

        Formato chileno: 56 9 XXXXXXXX (11 dígitos totales)
        - 56: código de país (constante)
        - 9: prefijo móvil (constante)
        - XXXXXXXX: 8 dígitos únicos del usuario

        Args:
            phone_number (str): Número telefónico ingresado por el usuario

        Returns:
            dict: {
                'db_number': str,  # Últimos 8 dígitos para guardar/consultar en BD
                'full_number': str  # Número completo con código país (56912345678) para enviar WhatsApp
            }

        Ejemplos:
            Input: "12345678" -> {'db_number': '12345678', 'full_number': '56912345678'}
            Input: "912345678" -> {'db_number': '12345678', 'full_number': '56912345678'}
            Input: "56912345678" -> {'db_number': '12345678', 'full_number': '56912345678'}
        """
        # Limpiar el número (remover espacios y caracteres especiales)
        clean_number = ''.join(filter(str.isdigit, phone_number))

        # Caso 1: Número completo con código de país (56912345678 - 11 dígitos)
        if clean_number.startswith('569') and len(clean_number) == 11:
            db_number = clean_number[-8:]  # Últimos 8 dígitos
            full_number = clean_number

        # Caso 2: Número con prefijo móvil pero sin código país (912345678 - 9 dígitos)
        elif clean_number.startswith('9') and len(clean_number) == 9:
            db_number = clean_number[-8:]  # Últimos 8 dígitos
            full_number = f"56{clean_number}"  # Agregar solo el 56 al inicio

        # Caso 3: Solo los 8 dígitos del usuario (12345678 - 8 dígitos)
        elif len(clean_number) == 8:
            db_number = clean_number
            full_number = f"569{clean_number}"  # Agregar 569 al inicio

        # Caso 4: Formato no reconocido
        else:
            # Si no coincide con ningún patrón, intentar extraer los últimos 8 dígitos
            if len(clean_number) >= 8:
                db_number = clean_number[-8:]
                # Intentar construir el número completo
                if clean_number.startswith('56'):
                    # Ya tiene código de país, verificar si tiene el 9
                    remaining = clean_number[2:]
                    if remaining.startswith('9'):
                        full_number = f"56{remaining}"
                    else:
                        full_number = f"569{db_number}"
                else:
                    full_number = f"569{db_number}"
            else:
                # Número muy corto, retornar tal cual
                db_number = clean_number
                full_number = f"569{clean_number}"

        return {
            'db_number': db_number,
            'full_number': full_number
        }

    @staticmethod
    def normalize_phone_by_country(phone_number, country, lada=None):
        """
        Normaliza un número telefónico según el país.

        Args:
            phone_number (str): Número telefónico ingresado
            country (str): Nombre del país
            lada (str, optional): Código de país (lada)

        Returns:
            dict: {
                'db_number': str,  # Número para guardar/consultar en BD
                'full_number': str  # Número completo para enviar WhatsApp
            }
        """
        # Por ahora solo manejamos Chile de manera especial
        if country == 'Chile':
            return PhoneNumberHandler.normalize_chile_phone(phone_number)

        # Para otros países, mantener el comportamiento actual
        # (no normalizar, usar el número tal cual)
        clean_number = ''.join(filter(str.isdigit, phone_number))

        if lada:
            # Si el número ya tiene el lada al inicio, no duplicarlo
            if clean_number.startswith(lada):
                full_number = clean_number
            else:
                full_number = f"{lada}{clean_number}"
        else:
            full_number = clean_number

        return {
            'db_number': clean_number,
            'full_number': full_number
        }
