"""
Tests para la sincronización de Google Sheets.

Ejecutar con:
    python manage.py test adm.tests.TestGoogleSheetSync
"""

from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch, MagicMock
import json

from adm.models import Account, Service, Business, User
from adm.functions.sync_google_sheets import SheetsSyncManager, sync_google_sheets


class TestGoogleSheetSync(TestCase):
    """Tests para la sincronización de Google Sheets"""
    
    def setUp(self):
        """Configurar datos de prueba"""
        # Crear business
        self.business = Business.objects.create(
            name="Test Business",
            email="test@example.com",
            url="http://test.com",
            phone_number="+1234567890"
        )
        
        # Crear usuario
        self.user = User.objects.create(
            username="testuser",
            email="testuser@example.com"
        )
        
        # Crear servicio
        self.service = Service.objects.create(
            description="NETFLIX",
            perfil_quantity=4,
            status=True
        )
        
        # Crear segundo servicio
        self.service_hbo = Service.objects.create(
            description="MAX",
            perfil_quantity=4,
            status=True
        )
    
    def test_validate_record_valid(self):
        """Test de validación de registro válido"""
        manager = SheetsSyncManager()
        
        record = {
            "EMAIL": "test@example.com",
            "CLAVE": "password123",
            "SERVICIO": "NETFLIX",
            "ACCOUNT NAME ID": self.service.id
        }
        
        is_valid, error = manager.validate_record(record)
        self.assertTrue(is_valid)
        self.assertEqual(error, "")
    
    def test_validate_record_empty_email(self):
        """Test de validación con email vacío"""
        manager = SheetsSyncManager()
        
        record = {
            "EMAIL": "",
            "CLAVE": "password123",
            "SERVICIO": "NETFLIX",
            "ACCOUNT NAME ID": self.service.id
        }
        
        is_valid, error = manager.validate_record(record)
        self.assertFalse(is_valid)
        self.assertIn("EMAIL", error)
    
    def test_validate_record_empty_password(self):
        """Test de validación con contraseña vacía"""
        manager = SheetsSyncManager()
        
        record = {
            "EMAIL": "test@example.com",
            "CLAVE": "",
            "SERVICIO": "NETFLIX",
            "ACCOUNT NAME ID": self.service.id
        }
        
        is_valid, error = manager.validate_record(record)
        self.assertFalse(is_valid)
        self.assertIn("CLAVE", error)
    
    def test_group_by_sheet(self):
        """Test de agrupación por nombre de hoja"""
        manager = SheetsSyncManager()
        
        data = [
            {"sheetName": "Account name", "EMAIL": "test1@example.com"},
            {"sheetName": "Account name", "EMAIL": "test2@example.com"},
            {"sheetName": "Vencidos", "EMAIL": "test3@example.com"},
        ]
        
        grouped = manager.group_by_sheet(data)
        
        self.assertEqual(len(grouped["Account name"]), 2)
        self.assertEqual(len(grouped["Vencidos"]), 1)
    
    def test_create_new_account(self):
        """Test de creación de nueva cuenta"""
        manager = SheetsSyncManager()
        
        record = {
            "EMAIL": "newuser@example.com",
            "CLAVE": "password123",
            "SERVICIO": "NETFLIX",
            "ACCOUNT NAME ID": self.service.id,
            "STATUS": "ACTIVA",
            "PERFIL": 2
        }
        
        # Validar y procesar
        is_valid, _ = manager.validate_record(record)
        self.assertTrue(is_valid)
        
        # Simular creación
        account = Account(
            email=record["EMAIL"],
            password=record["CLAVE"],
            account_name=self.service,
            status=1 if record["STATUS"] == "ACTIVA" else 0,
            profile=record["PERFIL"],
            business_id=self.business.id,
            created_by_id=self.user.id,
            modified_by_id=self.user.id,
            supplier_id=1,
            created_at=timezone.now(),
            expiration_date=timezone.now() + timedelta(days=30)
        )
        
        self.assertEqual(account.email, "newuser@example.com")
        self.assertEqual(account.password, "password123")
        self.assertEqual(account.status, 1)
    
    def test_update_account_password(self):
        """Test de actualización de contraseña"""
        # Crear cuenta existente
        account = Account.objects.create(
            email="test@example.com",
            password="oldpassword",
            account_name=self.service,
            status=1,
            profile=2,
            business_id=self.business.id,
            created_by_id=self.user.id,
            modified_by_id=self.user.id,
            supplier_id=1,
            created_at=timezone.now(),
            expiration_date=timezone.now() + timedelta(days=30)
        )
        
        # Actualizar contraseña
        old_password = account.password
        account.password = "newpassword"
        account.save()
        
        # Verificar
        self.assertEqual(account.password, "newpassword")
        self.assertNotEqual(account.password, old_password)
    
    @patch('adm.functions.sync_google_sheets.requests.post')
    def test_fetch_sheets_data(self, mock_post):
        """Test de obtención de datos de Google Sheets"""
        manager = SheetsSyncManager()
        
        # Mock de respuesta
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "row_number": 2,
                "sheetName": "Account name",
                "EMAIL": "test@example.com",
                "CLAVE": "password123",
                "SERVICIO": "NETFLIX",
                "ACCOUNT NAME ID": self.service.id,
                "STATUS": "ACTIVA"
            }
        ]
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        
        data = manager.fetch_sheets_data()
        
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["EMAIL"], "test@example.com")
    
    @patch('adm.functions.sync_google_sheets.requests.post')
    def test_fetch_sheets_data_error(self, mock_post):
        """Test de error al obtener datos"""
        manager = SheetsSyncManager()
        
        # Mock de error
        mock_post.side_effect = Exception("Connection error")
        
        data = manager.fetch_sheets_data()
        
        self.assertEqual(len(data), 0)
        self.assertEqual(len(manager.changes_log["errors"]), 1)


class TestSyncEndpoints(TestCase):
    """Tests para los endpoints de API"""
    
    @patch('adm.functions.sync_google_sheets.sync_google_sheets')
    def test_sync_sheets_endpoint(self, mock_sync):
        """Test del endpoint de sincronización"""
        from django.test import Client
        
        # Mock de respuesta
        mock_sync.return_value = {
            "total_updated": 5,
            "total_created": 2,
            "total_suspended": 1,
            "password_changes": 3,
            "status_changes": 2,
            "total_errors": 0,
            "timestamp": timezone.now().isoformat(),
            "details": {}
        }
        
        client = Client()
        response = client.post('/adm/api/sync-sheets/')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["summary"]["total_updated"], 5)
