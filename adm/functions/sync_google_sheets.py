"""
Sincronización de Google Sheets con la base de datos.
Reemplaza la lógica de n8n con un endpoint Django.
"""

import requests
import logging
from typing import List, Dict, Tuple
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Q

from adm.models import Account, Service
from adm.functions.send_whatsapp_notification import Notification


logger = logging.getLogger(__name__)

# Configuración
GOOGLE_SHEETS_API_URL = "https://servertools.bdpyc.cl/api/google-sheets"
GOOGLE_SHEET_ID = "1eY2EWKjarh1a909CLSrL22lP5HVUF5CZzdM9SDHBT3M"
BLACKLIST_SERVICES = ["YOUTUBE", "SPOTIFY"]  # No actualizar estos servicios de la misma forma


class SheetsSyncManager:
    """Gestor centralizado para sincronización de Google Sheets"""
    
    def __init__(self):
        self.logger = logger
        self.changes_log = {
            "updated": [],
            "created": [],
            "suspended": [],
            "password_changes": [],
            "status_changes": [],
            "errors": []
        }
    
    def fetch_sheets_data(self) -> List[Dict]:
        """
        Obtiene todos los datos de Google Sheets desde el endpoint.
        
        Returns:
            Lista de diccionarios con datos de las sheets
        """
        try:
            url = f"{GOOGLE_SHEETS_API_URL}/{GOOGLE_SHEET_ID}?format=n8n"
            response = requests.post(url, json={}, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # Debug: Log de los primeros 5 registros
            if data:
                self.logger.info(f"✅ Obtenidos {len(data)} registros de Google Sheets")
                self.logger.info(f"📋 Primeros 3 registros (para debug):")
                for idx, record in enumerate(data[:3]):
                    self.logger.info(f"   [{idx}] {record}")
            else:
                self.logger.warning("⚠️ No se obtuvieron registros de Google Sheets")
            
            return data
            
        except requests.exceptions.RequestException as e:
            error_msg = f"❌ Error al obtener datos de Google Sheets: {str(e)}"
            self.logger.error(error_msg)
            self.changes_log["errors"].append(error_msg)
            return []
    
    def group_by_sheet(self, data: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Agrupa datos por nombre de hoja de cálculo.
        
        Args:
            data: Lista de registros de Google Sheets
            
        Returns:
            Diccionario agrupado por sheetName
        """
        grouped = {}
        for record in data:
            sheet_name = record.get("sheetName", "Unknown")
            if sheet_name not in grouped:
                grouped[sheet_name] = []
            grouped[sheet_name].append(record)
        
        self.logger.info(f"📊 Datos agrupados en {len(grouped)} hojas: {list(grouped.keys())}")
        return grouped
    
    def validate_record(self, record: Dict) -> Tuple[bool, str]:
        """
        Valida si un registro tiene datos mínimos requeridos.
        
        Args:
            record: Diccionario con datos de la cuenta
            
        Returns:
            Tupla (es_válido, mensaje_error)
        """
        # Validaciones mínimas
        if not record.get("EMAIL") or not record.get("EMAIL").strip():
            return False, "EMAIL vacío"
        
        if not record.get("CLAVE") or not record.get("CLAVE"):
            return False, "CLAVE vacía"
        
        if not record.get("SERVICIO") or not record.get("SERVICIO").strip():
            return False, "SERVICIO vacío"
        
        # ACCOUNT NAME ID es OPCIONAL (puede venir de la hoja o del nombre de la hoja)
        # No lo validamos aquí
        
        return True, ""
    
    def get_account_name_id(self, service_name: str, sheet_name: str = None) -> int:
        """
        Obtiene el account_name_id (Service.id) desde:
        1. El nombre del servicio en el registro (SERVICIO)
        2. El nombre de la hoja (sheet_name)
        
        Args:
            service_name: Nombre del servicio (ej: "NETFLIX", "HBO")
            sheet_name: Nombre de la hoja (ej: "Netflix", "HBO Max")
            
        Returns:
            ID del servicio o None
        """
        try:
            # Intentar buscar por el nombre del servicio primero
            service = Service.objects.filter(
                description__icontains=service_name.split()[0].rstrip("1234567890")
            ).first()
            
            if service:
                return service.id
            
            # Si no encontró por servicio, intentar por nombre de hoja
            if sheet_name:
                service = Service.objects.filter(
                    description__icontains=sheet_name.split()[0]
                ).first()
                if service:
                    return service.id
            
            self.logger.warning(f"⚠️ No se encontró account_name para: {service_name} / {sheet_name}")
            return None
            
        except Exception as e:
            self.logger.warning(f"⚠️ Error obteniendo account_name para {service_name}: {str(e)}")
            return None
    
    
    def sync_accounts(self, grouped_data: Dict[str, List[Dict]]):
        """
        Sincroniza todas las cuentas desde Google Sheets.
        Maneja: actualizaciones y creaciones.
        
        NOTA: Se ignoran las hojas "Vencidos", "Account name", "Spotify Premium" y "YouTube Premium"
        Procesa: Netflix, Disney+, HBO Max, Paramount+, etc.
        
        Args:
            grouped_data: Datos agrupados por sheetName
        """
        # Hojas a ignorar
        IGNORE_SHEETS = ["Vencidos", "Account name", "Spotify Premium", "YouTube Premium"]
        
        # Debug: Mostrar qué hojas tienen datos
        self.logger.info(f"📊 Hojas disponibles: {list(grouped_data.keys())}")
        for sheet_name, records in grouped_data.items():
            self.logger.info(f"   - {sheet_name}: {len(records)} registros")
        
        # Procesar todas las hojas EXCEPTO las ignoradas
        for sheet_name, records in grouped_data.items():
            # IGNORAR hojas específicas PRIMERO
            if sheet_name in IGNORE_SHEETS:
                self.logger.info(f"📌 Hoja '{sheet_name}' ignorada completamente ({len(records)} registros descartados)")
                continue
            
            # Solo para hojas que NO están ignoradas
            self.logger.info(f"🔄 Procesando hoja '{sheet_name}' con {len(records)} registros")
            
            # Debug: Mostrar primeros 2 registros de cada hoja
            for idx, rec in enumerate(records[:2]):
                self.logger.info(f"   [Registro {idx}] EMAIL={rec.get('EMAIL')}, SERVICIO={rec.get('SERVICIO')}, CLAVE={rec.get('CLAVE')}")
            
            self._sync_password_updates(records, sheet_name)
    
    def _sync_password_updates(self, records: List[Dict], sheet_name: str = None):
        """
        Sincroniza cuentas desde la hoja especificada.
        
        Operaciones:
        - Actualiza cuentas existentes (contraseña, external_status, perfil)
        - CREA nuevas cuentas (sin notificaciones)
        
        Notificaciones (SOLO en actualizaciones, NO en creaciones):
        - WhatsApp: Solo si contraseña cambió y cuenta tiene cliente
        - Email: Solo si contraseña cambió y cliente tiene email en auth_user
        
        Args:
            records: Lista de registros de la hoja
            sheet_name: Nombre de la hoja (ej: "Netflix", "HBO Max")
        """
        self.logger.info("🔄 Procesando cuentas desde Google Sheets...")
        
        # Obtener account_name_id una sola vez para toda la hoja
        account_name_id = None
        if sheet_name:
            first_record = next((r for r in records if r.get("SERVICIO")), None)
            if first_record:
                account_name_id = self.get_account_name_id(first_record.get("SERVICIO"), sheet_name)
                self.logger.info(f"📋 Account Name ID para '{sheet_name}': {account_name_id}")
        
        for record in records:
            # Validar registro
            is_valid, error_msg = self.validate_record(record)
            if not is_valid:
                self.logger.warning(f"⏭️ Saltando registro inválido: {error_msg}")
                continue
            
            email = record.get("EMAIL").strip()
            clave = str(record.get("CLAVE")).strip()
            servicio = record.get("SERVICIO").strip()
            status_sheets = record.get("STATUS", "ACTIVA").upper()
            perfil = record.get("PERFIL", 1)
            
            try:
                # Mapear STATUS: ACTIVA → Disponible, resto igual
                external_status_value = "Disponible" if status_sheets == "ACTIVA" else status_sheets
                
                # Buscar cuenta existente por email + account_name_id
                # IMPORTANTE: Usar select_related para cargar customer y userdetail de una vez (optimización + notificaciones)
                if account_name_id:
                    account = Account.objects.select_related('customer', 'customer__userdetail', 'account_name').filter(
                        email=email,
                        account_name_id=account_name_id
                    ).first()
                else:
                    # Si no se encontró account_name, buscar por email + servicio
                    service_id = self.get_account_name_id(servicio, sheet_name)
                    if service_id:
                        account = Account.objects.select_related('customer', 'customer__userdetail', 'account_name').filter(
                            email=email,
                            account_name_id=service_id
                        ).first()
                    else:
                        account = None
                
                if account:
                    # ===== ACTUALIZAR cuenta existente =====
                    old_password = account.password
                    old_external_status = account.external_status
                    
                    # Actualizar campos
                    account.password = clave
                    account.external_status = external_status_value
                    account.profile = perfil
                    account.save(update_fields=['password', 'external_status', 'profile'])
                    
                    # Registrar cambio de contraseña
                    password_changed = old_password != clave
                    status_changed = old_external_status != external_status_value
                    
                    # Registrar cambios específicos
                    changes_made = []
                    if password_changed:
                        changes_made.append(f"contraseña ({old_password} → {clave})")
                        self.changes_log["password_changes"].append({
                            "email": email,
                            "servicio": servicio,
                            "old_password": old_password,
                            "new_password": clave
                        })
                        
                        # 📱 Notificar por WhatsApp SOLO si contraseña cambió y tiene cliente
                        self._notify_password_change_whatsapp(account, clave)
                        
                        # 📧 Notificar por Email SOLO si contraseña cambió y cliente tiene email
                        self._notify_password_change_email(account, clave)
                    
                    if status_changed:
                        changes_made.append(f"estado ({old_external_status} → {external_status_value})")
                        self.changes_log["status_changes"].append({
                            "email": email,
                            "servicio": servicio,
                            "old_status": old_external_status,
                            "new_status": external_status_value
                        })
                    
                    if not changes_made:
                        # Si nada cambió pero la cuenta existe
                        self.logger.info(f"ℹ️ Sin cambios: {email} ({servicio})")
                    else:
                        # Log detallado con cambios específicos
                        changes_str = ", ".join(changes_made)
                        self.logger.info(f"✏️ Actualizada cuenta: {email} ({servicio}) - {changes_str}")
                    
                    self.changes_log["updated"].append({
                        "email": email,
                        "servicio": servicio,
                        "password_changed": password_changed,
                        "status_changed": status_changed
                    })
                
                else:
                    # ===== CREAR nueva cuenta (sin notificaciones) =====
                    try:
                        # Obtener servicio
                        service_id = account_name_id or self.get_account_name_id(servicio, sheet_name)
                        if not service_id:
                            self.logger.warning(f"⚠️ Servicio no encontrado: {servicio}")
                            self.changes_log["errors"].append(f"Servicio no encontrado: {servicio}")
                            continue
                        
                        # Crear cuenta
                        new_account = Account.objects.create(
                            email=email,
                            password=clave,
                            account_name_id=service_id,
                            business_id=1,  # Por defecto
                            supplier_id=7,  # Proveedor Cuentas México
                            created_by_id=1,  # Por defecto (admin)
                            modified_by_id=1,  # Por defecto (admin)
                            external_status=external_status_value,
                            profile=perfil,
                            expiration_date=timezone.now() + timedelta(days=30)  # 30 días por defecto
                        )
                        
                        self.changes_log["created"].append({
                            "email": email,
                            "servicio": servicio
                        })
                        
                        self.logger.info(f"✅ Cuenta creada: {email} ({servicio})")
                        
                    except Exception as create_error:
                        error = f"❌ Error creando cuenta {email}: {str(create_error)}"
                        self.logger.error(error)
                        self.changes_log["errors"].append(error)
                    
            except Exception as e:
                error = f"❌ Error procesando {email}: {str(e)}"
                self.logger.error(error)
                self.changes_log["errors"].append(error)
    
    def _notify_password_change_whatsapp(self, account: Account, new_password: str):
        """
        Envía notificación por WhatsApp solo si:
        - La cuenta tiene cliente asignado
        - El cliente tiene userdetail con phone_number
        
        Args:
            account: Instancia de Account
            new_password: Nueva contraseña
        """
        try:
            if not account.customer:
                self.logger.info(f"ℹ️ No hay cliente asignado a {account.email} - Sin notificación WhatsApp")
                return
            
            if not hasattr(account.customer, 'userdetail'):
                self.logger.info(f"ℹ️ Cliente de {account.email} sin userdetail - Sin notificación WhatsApp")
                return
            
            phone = account.customer.userdetail.phone_number
            lada = account.customer.userdetail.lada
            
            # Obtener fecha de vencimiento de la última venta activa
            from adm.models import Sale
            from django.utils import timezone
            import pytz
            
            last_sale = Sale.objects.filter(account=account, status=True).order_by('-expiration_date').first()
            if last_sale and last_sale.expiration_date:
                # Convertir a zona horaria de Ciudad de México
                mexico_tz = pytz.timezone('America/Mexico_City')
                expiration_local = last_sale.expiration_date.astimezone(mexico_tz)
                expiration_str = expiration_local.strftime('%d/%m/%Y')
            else:
                expiration_str = 'No definida'
            
            message = f"""
🔐 *Cambio de Contraseña*

Tu contraseña para *{account.account_name.description}* ha sido actualizada:

📧 Email: {account.email}
🔑 Nueva contraseña: {new_password}
👤 Perfil: {account.profile}
📅 Vence: {expiration_str}

¡Guarda este mensaje en un lugar seguro!
            """
            
            Notification.send_whatsapp_notification(message.strip(), lada, phone)
            self.logger.info(f"📱 Notificación WhatsApp enviada a {lada}{phone}")
        except Exception as e:
            self.logger.warning(f"⚠️ Error enviando WhatsApp a {account.email}: {str(e)}")
    
    def _notify_password_change_email(self, account: Account, new_password: str):
        """
        Envía notificación por email solo si:
        - La cuenta tiene cliente asignado
        - El cliente tiene email en auth_user
        
        Usa Resend para enviar el email
        
        Args:
            account: Instancia de Account
            new_password: Nueva contraseña
        """
        try:
            if not account.customer:
                self.logger.info(f"ℹ️ No hay cliente asignado a {account.email} - Sin notificación email")
                return
            
            customer_email = account.customer.email
            if not customer_email:
                self.logger.info(f"ℹ️ Cliente de {account.email} sin email - Sin notificación email")
                return
            
            # Importar Resend aquí para evitar dependencias innecesarias
            try:
                import resend
            except ImportError:
                self.logger.warning(f"⚠️ Librería 'resend' no instalada - No se envió email a {customer_email}")
                return
            
            subject = f"🔐 Tu contraseña de {account.account_name.description} ha sido actualizada"
            
            # Obtener fecha de vencimiento de la última venta activa
            from adm.models import Sale
            from django.utils import timezone
            import pytz
            
            last_sale = Sale.objects.filter(account=account, status=True).order_by('-expiration_date').first()
            if last_sale and last_sale.expiration_date:
                # Convertir a zona horaria de Ciudad de México
                mexico_tz = pytz.timezone('America/Mexico_City')
                expiration_local = last_sale.expiration_date.astimezone(mexico_tz)
                expiration_str = expiration_local.strftime('%d/%m/%Y')
            else:
                expiration_str = 'No definida'
            
            html_content = f"""
            <html>
                <body style="font-family: Arial, sans-serif;">
                    <h2>🔐 Cambio de Contraseña</h2>
                    <p>Tu contraseña para <strong>{account.account_name.description}</strong> ha sido actualizada:</p>
                    <ul>
                        <li><strong>📧 Email:</strong> {account.email}</li>
                        <li><strong>🔑 Nueva contraseña:</strong> {new_password}</li>
                        <li><strong>👤 Perfil:</strong> {account.profile}</li>
                        <li><strong>📅 Fecha de vencimiento:</strong> {expiration_str}</li>
                    </ul>
                    <p style="color: red;"><strong>¡Guarda este mensaje en un lugar seguro!</strong></p>
                </body>
            </html>
            """
            
            # Enviar con Resend
            resend.Emails.send({
                "from": "noreply@cuentasmexico.mx",
                "to": customer_email,
                "subject": subject,
                "html": html_content
            })
            
            self.logger.info(f"📧 Email enviado a {customer_email}")
        except Exception as e:
            self.logger.warning(f"⚠️ Error enviando email a {account.email}: {str(e)}")
    
    def get_summary(self) -> Dict:
        """
        Retorna un resumen de cambios realizados.
        
        Returns:
            Diccionario con estadísticas de cambios
        """
        return {
            "total_updated": len(self.changes_log["updated"]),
            "total_created": len(self.changes_log["created"]),
            "total_suspended": len(self.changes_log["suspended"]),
            "password_changes": len(self.changes_log["password_changes"]),
            "status_changes": len(self.changes_log["status_changes"]),
            "total_errors": len(self.changes_log["errors"]),
            "timestamp": timezone.now().isoformat(),
            "details": self.changes_log
        }
    
    def verify_accounts_exist(self):
        """
        Coteja todas las cuentas del Excel con las de BD (supplier_id=7).
        Si una cuenta existe en BD pero NO en el Excel:
        - Cambia external_status a "deleted"
        - Cambia status a False (0)
        
        IMPORTANTE: Solo compara emails exactos (case-insensitive, sin espacios)
        
        Retorna:
            dict: Resumen con cuentas eliminadas y errores
        """
        self.logger.info("🔍 Verificando cuentas eliminadas del Excel...")
        
        deleted_summary = {
            "marked_as_deleted": 0,
            "deleted_accounts": [],
            "errors": [],
            "debug_info": {}
        }
        
        try:
            # Obtener todas las cuentas del Excel
            sheets_data = self.fetch_sheets_data()
            excel_accounts = set()
            
            # Extraer emails de todas las hojas (excepto ignoradas)
            IGNORE_SHEETS = ["Vencidos", "Account name", "Spotify Premium", "YouTube Premium"]
            
            # El API retorna una lista plana de registros, no agrupados por hoja
            for record in sheets_data:
                sheet_name = record.get("sheetName", "")
                
                # Ignorar hojas específicas
                if sheet_name in IGNORE_SHEETS:
                    continue
                
                # Obtener email tal como viene del API
                email_raw = record.get("EMAIL")
                if email_raw:
                    # Normalizar: strip whitespace y lowercase
                    email_normalized = str(email_raw).strip().lower()
                    if email_normalized:  # Solo agregar si no está vacío después del strip
                        excel_accounts.add(email_normalized)
            
            self.logger.info(f"📋 Total cuentas en Excel (válidas): {len(excel_accounts)}")
            
            # DEBUG: Mostrar primeros 10 emails del Excel para verificación
            excel_sample = sorted(list(excel_accounts))[:10]
            self.logger.info(f"📋 Sample de emails en Excel (primeros 10): {excel_sample}")
            deleted_summary["debug_info"]["excel_sample"] = excel_sample
            
            # Obtener todas las cuentas de BD con supplier_id = 7 Y status = True
            bd_accounts = Account.objects.filter(
                supplier_id=7,
                status=True  # Solo las activas
            ).values('id', 'email', 'external_status', 'account_name__description').order_by('email')
            
            self.logger.info(f"💾 Total cuentas en BD (supplier_id=7, status=True): {bd_accounts.count()}")
            
            # DEBUG: Mostrar primeros 10 emails de BD para verificación
            bd_sample = []
            for idx, account in enumerate(bd_accounts[:10]):
                bd_email_normalized = account['email'].strip().lower()
                bd_sample.append({
                    "id": account['id'],
                    "email_raw": account['email'],
                    "email_normalized": bd_email_normalized,
                    "exists_in_excel": bd_email_normalized in excel_accounts
                })
            
            self.logger.info(f"💾 Sample de emails en BD (primeros 10):")
            for sample in bd_sample:
                self.logger.info(f"   {sample}")
            
            deleted_summary["debug_info"]["bd_sample"] = bd_sample
            
            # Comparar: cuentas en BD que NO están en Excel
            accounts_to_delete = []
            
            for account in bd_accounts:
                # Normalizar email: strip whitespace y lowercase
                bd_email_normalized = account['email'].strip().lower()
                
                # Si NO está en el Excel, marcar como deleted
                if bd_email_normalized not in excel_accounts:
                    accounts_to_delete.append(account)
            
            self.logger.info(f"🗑️  Encontradas {len(accounts_to_delete)} cuentas que NO están en Excel")
            
            # Procesar solo si hay cuentas para eliminar
            if accounts_to_delete:
                self.logger.info("⚠️  ADVERTENCIA: Hay cuentas para marcar como deleted:")
                for account in accounts_to_delete[:10]:  # Mostrar primeras 10
                    self.logger.info(f"   - {account['email']} ({account['account_name__description']})")
                
                # VERIFICACIÓN: Mostrar si vania03@capibaraa.in está siendo marcada
                for account in accounts_to_delete:
                    if 'vania03@capibaraa.in' in account['email'].lower():
                        self.logger.error(f"❌ PROBLEMA DETECTADO: vania03@capibaraa.in será marcada como deleted!")
                        self.logger.error(f"   Email raw: '{account['email']}'")
                        self.logger.error(f"   Email normalized: '{account['email'].strip().lower()}'")
                        self.logger.error(f"   ¿Está en excel_accounts? {account['email'].strip().lower() in excel_accounts}")
            
            # NO ejecutar el borrado hasta que verifiques el debug
            # Por ahora solo retornar debug info
            
            # Mostrar resumen
            self.logger.info(f"""
╔════════════════════════════════════════╗
║   VERIFICACIÓN DE CUENTAS COMPLETADA   ║
╚════════════════════════════════════════╝
  🗑️  Cuentas a marcar como deleted: {len(accounts_to_delete)} (NO SE BORRARON - MODO DEBUG)
  ❌ Errores: {len(deleted_summary['errors'])}
            """)
            
            for account in accounts_to_delete:
                try:
                    acc_obj = Account.objects.get(id=account['id'])
                    old_status = acc_obj.external_status
                    
                    # Actualizar
                    acc_obj.external_status = "deleted"
                    acc_obj.status = False
                    acc_obj.save(update_fields=['external_status', 'status'])
                    
                    deleted_summary["marked_as_deleted"] += 1
                    deleted_summary["deleted_accounts"].append({
                        "id": account['id'],
                        "email": account['email'],
                        "servicio": account['account_name__description'],
                        "old_status": old_status,
                        "new_status": "deleted"
                    })
                    
                    self.logger.info(f"🗑️ Marcada como deleted: {account['email']} ({account['account_name__description']})")
                    
                except Exception as e:
                    error = f"❌ Error marcando cuenta {account['email']} como deleted: {str(e)}"
                    self.logger.error(error)
                    deleted_summary["errors"].append(error)
            
            # Mostrar resumen
            self.logger.info(f"""
╔════════════════════════════════════════╗
║   VERIFICACIÓN DE CUENTAS COMPLETADA   ║
╚════════════════════════════════════════╝
  📋 Cuentas en Excel: {len(excel_accounts)}
  💾 Cuentas en BD: {bd_accounts.count()}
  🗑️  Cuentas marcadas como deleted: {deleted_summary['marked_as_deleted']}
  ❌ Errores: {len(deleted_summary['errors'])}
            """)
            
            return deleted_summary
            
        except Exception as e:
            error = f"❌ Error crítico en verificación: {str(e)}"
            self.logger.error(error)
            import traceback
            self.logger.error(traceback.format_exc())
            deleted_summary["errors"].append(error)
            return deleted_summary


def sync_google_sheets():
    """
    Función principal para sincronizar Google Sheets con la BD.
    Puede llamarse desde una tarea programada, webhook o cron.
    
    Returns:
        Diccionario con resumen de cambios
    """
    manager = SheetsSyncManager()
    
    try:
        # Obtener datos
        sheets_data = manager.fetch_sheets_data()
        if not sheets_data:
            return manager.get_summary()
        
        # Agrupar por hoja
        grouped_data = manager.group_by_sheet(sheets_data)
        
        # Sincronizar
        manager.sync_accounts(grouped_data)
        
        # Log final
        summary = manager.get_summary()
        logger.info(f"""
📊 SINCRONIZACIÓN COMPLETADA
  ✏️ Actualizadas: {summary['total_updated']}
  ✨ Creadas: {summary['total_created']}
  ⏸️ Suspendidas: {summary['total_suspended']}
  🔐 Cambios de contraseña: {summary['password_changes']}
  📊 Cambios de estado: {summary['status_changes']}
  ❌ Errores: {summary['total_errors']}
        """)
        
        return summary
        
    except Exception as e:
        logger.error(f"❌ Error crítico en sincronización: {str(e)}")
        return manager.get_summary()
