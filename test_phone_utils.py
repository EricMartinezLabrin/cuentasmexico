#!/usr/bin/env python3
"""
Test simple para la normalización de números chilenos
Sin necesidad de Django test runner
"""

import sys
sys.path.insert(0, '/home/luinmack/proyects/CuentasMexico/legacy/cuentasmexico')

from index.phone_utils import PhoneNumberHandler


def test_normalize_chile_8_digits():
    """Test: Usuario ingresa solo 8 dígitos (12345678)"""
    result = PhoneNumberHandler.normalize_chile_phone("12345678")
    assert result['db_number'] == "12345678", f"Expected '12345678', got '{result['db_number']}'"
    assert result['full_number'] == "56912345678", f"Expected '56912345678', got '{result['full_number']}'"
    print("✓ Test 8 dígitos: PASSED")


def test_normalize_chile_9_digits_with_prefix():
    """Test: Usuario ingresa 9 dígitos con prefijo móvil (912345678)"""
    result = PhoneNumberHandler.normalize_chile_phone("912345678")
    assert result['db_number'] == "12345678", f"Expected '12345678', got '{result['db_number']}'"
    assert result['full_number'] == "56912345678", f"Expected '56912345678', got '{result['full_number']}'"
    print("✓ Test 9 dígitos con prefijo: PASSED")


def test_normalize_chile_11_digits_full():
    """Test: Usuario ingresa número completo con código país (56912345678)"""
    result = PhoneNumberHandler.normalize_chile_phone("56912345678")
    assert result['db_number'] == "12345678", f"Expected '12345678', got '{result['db_number']}'"
    assert result['full_number'] == "56912345678", f"Expected '56912345678', got '{result['full_number']}'"
    print("✓ Test 11 dígitos completo: PASSED")


def test_normalize_chile_with_spaces():
    """Test: Usuario ingresa número con espacios (56 9 12345678)"""
    result = PhoneNumberHandler.normalize_chile_phone("56 9 12345678")
    assert result['db_number'] == "12345678", f"Expected '12345678', got '{result['db_number']}'"
    assert result['full_number'] == "56912345678", f"Expected '56912345678', got '{result['full_number']}'"
    print("✓ Test con espacios: PASSED")


def test_normalize_chile_with_special_chars():
    """Test: Usuario ingresa número con caracteres especiales (+56-9-12345678)"""
    result = PhoneNumberHandler.normalize_chile_phone("+56-9-12345678")
    assert result['db_number'] == "12345678", f"Expected '12345678', got '{result['db_number']}'"
    assert result['full_number'] == "56912345678", f"Expected '56912345678', got '{result['full_number']}'"
    print("✓ Test con caracteres especiales: PASSED")


def test_normalize_phone_by_country_chile():
    """Test: normalize_phone_by_country para Chile"""
    result = PhoneNumberHandler.normalize_phone_by_country("912345678", "Chile")
    assert result['db_number'] == "12345678", f"Expected '12345678', got '{result['db_number']}'"
    assert result['full_number'] == "56912345678", f"Expected '56912345678', got '{result['full_number']}'"
    print("✓ Test normalize_phone_by_country Chile: PASSED")


def test_normalize_phone_by_country_mexico_10_digits():
    """Test: normalize_phone_by_country México - Usuario ingresa 10 dígitos"""
    result = PhoneNumberHandler.normalize_phone_by_country("5512345678", "México")
    assert result['db_number'] == "5512345678", f"Expected '5512345678', got '{result['db_number']}'"
    assert result['full_number'] == "5215512345678", f"Expected '5215512345678', got '{result['full_number']}'"
    print("✓ Test México 10 dígitos: PASSED")


def test_normalize_phone_by_country_mexico_with_52():
    """Test: normalize_phone_by_country México - Usuario incluye 52 pero sin el 1"""
    result = PhoneNumberHandler.normalize_phone_by_country("525512345678", "México")
    assert result['db_number'] == "525512345678", f"Expected '525512345678', got '{result['db_number']}'"
    assert result['full_number'] == "5215512345678", f"Expected '5215512345678', got '{result['full_number']}'"
    print("✓ Test México con 52 (sin 1): PASSED")


def test_normalize_phone_by_country_mexico_full():
    """Test: normalize_phone_by_country México - Usuario ingresa número completo con 521"""
    result = PhoneNumberHandler.normalize_phone_by_country("5215512345678", "México")
    assert result['db_number'] == "5215512345678", f"Expected '5215512345678', got '{result['db_number']}'"
    assert result['full_number'] == "5215512345678", f"Expected '5215512345678', got '{result['full_number']}'"
    print("✓ Test México número completo (521): PASSED")


def test_different_chile_formats():
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
        assert result['db_number'] == "12345678", \
            f"db_number failed for format: {phone_format}, got {result['db_number']}"
        assert result['full_number'] == "56912345678", \
            f"full_number failed for format: {phone_format}, got {result['full_number']}"

    print("✓ Test diferentes formatos: PASSED")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("TESTING: Normalización de números telefónicos")
    print("="*60 + "\n")

    try:
        # Tests de Chile
        print("--- Tests para Chile ---")
        test_normalize_chile_8_digits()
        test_normalize_chile_9_digits_with_prefix()
        test_normalize_chile_11_digits_full()
        test_normalize_chile_with_spaces()
        test_normalize_chile_with_special_chars()
        test_normalize_phone_by_country_chile()
        test_different_chile_formats()

        # Tests de México
        print("\n--- Tests para México ---")
        test_normalize_phone_by_country_mexico_10_digits()
        test_normalize_phone_by_country_mexico_with_52()
        test_normalize_phone_by_country_mexico_full()

        print("\n" + "="*60)
        print("✓ TODOS LOS TESTS PASARON EXITOSAMENTE")
        print("="*60 + "\n")

    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ ERROR: {e}\n")
        sys.exit(1)
