"""
API endpoints para sincronización de Google Sheets.
"""

from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import logging

from adm.functions.sync_google_sheets import sync_google_sheets, SheetsSyncManager


logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST"])
def sync_sheets_endpoint(request):
    """
    Endpoint para sincronizar Google Sheets con la base de datos.
    
    Métodos: POST
    
    Query params:
        - format: 'json' (default) o 'verbose'
    
    Returns:
        {
            "status": "success|error",
            "message": "Descripción",
            "summary": {
                "total_updated": int,
                "total_created": int,
                "total_suspended": int,
                "password_changes": int,
                "status_changes": int,
                "total_errors": int,
                "details": {...}
            }
        }
    
    Ejemplo de uso:
        curl -X POST http://localhost:8000/api/sync-sheets/
    """
    
    try:
        # Ejecutar sincronización
        summary = sync_google_sheets()
        
        # Preparar respuesta
        response_data = {
            "status": "success",
            "message": f"Sincronización completada: {summary['total_updated']} actualizadas, {summary['total_created']} creadas, {summary['total_suspended']} suspendidas",
            "summary": summary
        }
        
        # Log
        logger.info(f"✅ Sincronización exitosa: {summary['total_updated']} actualiz., {summary['total_created']} creat., {summary['total_suspended']} susp.")
        
        return JsonResponse(response_data, status=200)
        
    except Exception as e:
        error_msg = f"Error en sincronización: {str(e)}"
        logger.error(f"❌ {error_msg}")
        
        return JsonResponse({
            "status": "error",
            "message": error_msg,
            "summary": None
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def sync_sheets_debug(request):
    """
    Endpoint de debug que muestra información detallada.
    Útil para testing y troubleshooting.
    
    Returns información completa incluyendo todos los registros procesados.
    """
    
    try:
        summary = sync_google_sheets()
        
        # Formato más verbose
        response_data = {
            "status": "success",
            "summary": summary,
            "debug_info": {
                "total_records_updated": summary['total_updated'],
                "updated_accounts": summary['details']['updated'],
                "created_accounts": summary['details']['created'],
                "suspended_accounts": summary['details']['suspended'],
                "password_changes_detail": summary['details']['password_changes'],
                "status_changes_detail": summary['details']['status_changes'],
                "errors": summary['details']['errors'],
                "timestamp": summary['timestamp']
            }
        }
        
        return JsonResponse(response_data, status=200)
        
    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def verify_accounts_endpoint(request):
    """
    Endpoint para verificar que todas las cuentas de BD (supplier_id=7)
    existan en el Excel. Si no están, se marcan como deleted.
    
    Métodos: POST
    
    Returns:
        {
            "status": "success|error",
            "message": "Descripción",
            "summary": {
                "marked_as_deleted": int,
                "deleted_accounts": [
                    {
                        "id": int,
                        "email": str,
                        "servicio": str,
                        "old_status": str,
                        "new_status": "deleted"
                    }
                ],
                "errors": []
            }
        }
    
    Ejemplo de uso:
        curl -X POST http://localhost:8000/api/verify-accounts/
    """
    
    try:
        # Ejecutar verificación
        manager = SheetsSyncManager()
        summary = manager.verify_accounts_exist()
        
        # Preparar respuesta
        response_data = {
            "status": "success",
            "message": f"Verificación completada: {summary['marked_as_deleted']} cuentas marcadas como deleted",
            "summary": summary
        }
        
        # Log
        logger.info(f"✅ Verificación exitosa: {summary['marked_as_deleted']} cuentas marcadas como deleted")
        
        return JsonResponse(response_data, status=200)
        
    except Exception as e:
        error_msg = f"Error en verificación: {str(e)}"
        logger.error(f"❌ {error_msg}")
        
        return JsonResponse({
            "status": "error",
            "message": error_msg,
            "summary": None
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def verify_accounts_debug(request):
    """
    Endpoint DEBUG para ver qué emails se están extrayendo del Excel vs BD.
    NO hace cambios, solo muestra información.
    """
    
    try:
        manager = SheetsSyncManager()
        
        # Obtener datos del Excel
        sheets_data = manager.fetch_sheets_data()
        excel_emails = set()
        
        IGNORE_SHEETS = ["Vencidos", "Account name", "Spotify Premium", "YouTube Premium"]
        
        sheets_info = []
        for sheet in sheets_data:
            sheet_name = sheet.get("sheetName", "")
            
            if sheet_name in IGNORE_SHEETS:
                continue
            
            records = sheet.get("records", [])
            sheet_emails = []
            for record in records:
                email = record.get("EMAIL")
                if email:
                    email = email.strip().lower()
                    excel_emails.add(email)
                    sheet_emails.append(email)
            
            sheets_info.append({
                "sheet_name": sheet_name,
                "total_records": len(records),
                "total_emails": len(sheet_emails),
                "sample_emails": sheet_emails[:3]
            })
        
        # Obtener datos de BD
        from adm.models import Account
        bd_accounts = Account.objects.filter(
            supplier_id=7,
            status=True
        ).values_list('email', flat=True)
        
        bd_emails = set(email.strip().lower() for email in bd_accounts)
        
        # Comparar
        only_in_bd = bd_emails - excel_emails
        only_in_excel = excel_emails - bd_emails
        in_both = bd_emails & excel_emails
        
        response_data = {
            "status": "debug",
            "excel_info": {
                "total_sheets_processed": len(sheets_info),
                "total_emails_found": len(excel_emails),
                "sheets": sheets_info,
                "sample_emails": list(excel_emails)[:10]
            },
            "bd_info": {
                "total_emails": len(bd_emails),
                "sample_emails": list(bd_emails)[:10]
            },
            "comparison": {
                "in_both": len(in_both),
                "only_in_bd": len(only_in_bd),
                "only_in_excel": len(only_in_excel),
                "only_in_bd_sample": list(only_in_bd)[:10],
                "only_in_excel_sample": list(only_in_excel)[:10]
            }
        }
        
        return JsonResponse(response_data, status=200)
        
    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": str(e)
        }, status=500)
