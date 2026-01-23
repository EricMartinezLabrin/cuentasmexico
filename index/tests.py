from django.test import TestCase
from index.phone_utils import PhoneNumberHandler


class PhoneNumberHandlerTestCase(TestCase):
    """Tests para la normalización de números telefónicos"""

    def test_normalize_chile_8_digits(self):
        """Test: Usuario ingresa solo 8 dígitos (12345678)"""
        result = PhoneNumberHandler.normalize_chile_phone("12345678")
        self.assertEqual(result['db_number'], "12345678")
        self.assertEqual(result['full_number'], "56912345678")

    def test_normalize_chile_9_digits_with_prefix(self):
        """Test: Usuario ingresa 9 dígitos con prefijo móvil (912345678)"""
        result = PhoneNumberHandler.normalize_chile_phone("912345678")
        self.assertEqual(result['db_number'], "12345678")
        self.assertEqual(result['full_number'], "56912345678")

    def test_normalize_chile_11_digits_full(self):
        """Test: Usuario ingresa número completo con código país (56912345678)"""
        result = PhoneNumberHandler.normalize_chile_phone("56912345678")
        self.assertEqual(result['db_number'], "12345678")
        self.assertEqual(result['full_number'], "56912345678")

    def test_normalize_chile_with_spaces(self):
        """Test: Usuario ingresa número con espacios (56 9 12345678)"""
        result = PhoneNumberHandler.normalize_chile_phone("56 9 12345678")
        self.assertEqual(result['db_number'], "12345678")
        self.assertEqual(result['full_number'], "56912345678")

    def test_normalize_chile_with_special_chars(self):
        """Test: Usuario ingresa número con caracteres especiales (+56-9-12345678)"""
        result = PhoneNumberHandler.normalize_chile_phone("+56-9-12345678")
        self.assertEqual(result['db_number'], "12345678")
        self.assertEqual(result['full_number'], "56912345678")

    def test_normalize_phone_by_country_chile(self):
        """Test: normalize_phone_by_country para Chile"""
        result = PhoneNumberHandler.normalize_phone_by_country("912345678", "Chile")
        self.assertEqual(result['db_number'], "12345678")
        self.assertEqual(result['full_number'], "56912345678")

    def test_normalize_phone_by_country_other(self):
        """Test: normalize_phone_by_country para otro país (México)"""
        result = PhoneNumberHandler.normalize_phone_by_country("5512345678", "México", lada="52")
        self.assertEqual(result['db_number'], "5512345678")
        self.assertEqual(result['full_number'], "525512345678")

    def test_normalize_phone_by_country_other_with_lada(self):
        """Test: normalize_phone_by_country cuando el número ya tiene lada"""
        result = PhoneNumberHandler.normalize_phone_by_country("525512345678", "México", lada="52")
        self.assertEqual(result['db_number'], "525512345678")
        self.assertEqual(result['full_number'], "525512345678")

    def test_different_chile_formats(self):
        """Test: Diferentes formatos de entrada producen el mismo resultado"""
        formats = [
            "12345678",
            "912345678",
            "56912345678",
            "+56 9 12345678",
            "56-9-12345678"
        ]

        for phone_format in formats:
            result = PhoneNumberHandler.normalize_chile_phone(phone_format)
            self.assertEqual(result['db_number'], "12345678",
                           f"Failed for format: {phone_format}")
            self.assertEqual(result['full_number'], "56912345678",
                           f"Failed for format: {phone_format}")
