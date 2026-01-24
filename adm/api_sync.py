"""
API endpoints para sincronización de Google Sheets.
Todos los endpoints ejecutan tareas en segundo plano para no bloquear el servidor.
"""

from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import logging

from adm.functions.sync_google_sheets import sync_google_sheets, SheetsSyncManager
from adm.functions.background_tasks import get_task_manager, TaskStatus


logger = logging.getLogger(__name__)


def _task_to_dict(task):
    """Convierte una BackgroundTask a diccionario para JSON"""
    if task is None:
        return None
    return {
        "task_id": task.task_id,
        "task_type": task.task_type,
        "status": task.status.value,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "progress": task.progress,
        "result": task.result,
        "error": task.error
    }


@csrf_exempt
@require_http_methods(["POST"])
def sync_sheets_endpoint(request):
    """
    Endpoint para sincronizar Google Sheets con la base de datos.
    La sincronización se ejecuta en segundo plano y retorna inmediatamente.

    Métodos: POST

    Returns:
        {
            "status": "started|already_running|error",
            "message": "Descripción",
            "task": {
                "task_id": str,
                "status": str,
                "started_at": str,
                ...
            }
        }

    Para consultar el estado:
        GET /api/sync-sheets/status/?task_id=<task_id>
        GET /api/sync-sheets/status/  (última tarea)
    """

    try:
        task_manager = get_task_manager()

        # Intentar iniciar la tarea
        success, message, task = task_manager.start_task(
            task_type="sync_sheets",
            func=sync_google_sheets
        )

        if success:
            logger.info(f"🚀 Sincronización iniciada en segundo plano: {task.task_id}")
            return JsonResponse({
                "status": "started",
                "message": message,
                "task": _task_to_dict(task)
            }, status=202)  # 202 Accepted
        else:
            # Ya hay una tarea corriendo
            logger.info(f"⏳ Sincronización ya en progreso: {task.task_id}")
            return JsonResponse({
                "status": "already_running",
                "message": message,
                "task": _task_to_dict(task)
            }, status=409)  # 409 Conflict

    except Exception as e:
        error_msg = f"Error iniciando sincronización: {str(e)}"
        logger.error(f"❌ {error_msg}")
        return JsonResponse({
            "status": "error",
            "message": error_msg,
            "task": None
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def sync_sheets_status(request):
    """
    Consulta el estado de una sincronización.

    Query params:
        - task_id: ID de la tarea (opcional, si no se envía retorna la última)

    Returns:
        {
            "status": "found|not_found",
            "task": { ... }
        }
    """
    task_manager = get_task_manager()
    task_id = request.GET.get('task_id')

    if task_id:
        task = task_manager.get_task(task_id)
    else:
        # Buscar la tarea más reciente de sync_sheets
        task = task_manager.get_running_task("sync_sheets")
        if not task:
            # Buscar la última completada
            all_tasks = task_manager.get_all_tasks()
            sync_tasks = [t for t in all_tasks.values() if t.task_type == "sync_sheets"]
            if sync_tasks:
                task = max(sync_tasks, key=lambda t: t.started_at or t.completed_at)

    if task:
        return JsonResponse({
            "status": "found",
            "task": _task_to_dict(task)
        })
    else:
        return JsonResponse({
            "status": "not_found",
            "message": "No se encontró la tarea",
            "task": None
        }, status=404)


@csrf_exempt
@require_http_methods(["POST"])
def sync_sheets_debug(request):
    """
    Endpoint de debug que ejecuta sincronización en segundo plano
    y retorna información de la tarea iniciada.
    """

    try:
        task_manager = get_task_manager()

        success, message, task = task_manager.start_task(
            task_type="sync_sheets_debug",
            func=sync_google_sheets
        )

        if success:
            return JsonResponse({
                "status": "started",
                "message": f"Debug sync iniciado. Consulta el estado en /api/sync-sheets/status/?task_id={task.task_id}",
                "task": _task_to_dict(task)
            }, status=202)
        else:
            return JsonResponse({
                "status": "already_running",
                "message": message,
                "task": _task_to_dict(task)
            }, status=409)

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
    existan en el Excel. Se ejecuta en segundo plano.

    Returns:
        {
            "status": "started|already_running|error",
            "message": "Descripción",
            "task": { ... }
        }

    Para consultar el estado:
        GET /api/verify-accounts/status/?task_id=<task_id>
    """

    def _run_verify():
        manager = SheetsSyncManager()
        return manager.verify_accounts_exist()

    try:
        task_manager = get_task_manager()

        success, message, task = task_manager.start_task(
            task_type="verify_accounts",
            func=_run_verify
        )

        if success:
            logger.info(f"🚀 Verificación iniciada en segundo plano: {task.task_id}")
            return JsonResponse({
                "status": "started",
                "message": message,
                "task": _task_to_dict(task)
            }, status=202)
        else:
            logger.info(f"⏳ Verificación ya en progreso: {task.task_id}")
            return JsonResponse({
                "status": "already_running",
                "message": message,
                "task": _task_to_dict(task)
            }, status=409)

    except Exception as e:
        error_msg = f"Error iniciando verificación: {str(e)}"
        logger.error(f"❌ {error_msg}")
        return JsonResponse({
            "status": "error",
            "message": error_msg,
            "task": None
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def verify_accounts_status(request):
    """
    Consulta el estado de una verificación de cuentas.

    Query params:
        - task_id: ID de la tarea (opcional)
    """
    task_manager = get_task_manager()
    task_id = request.GET.get('task_id')

    if task_id:
        task = task_manager.get_task(task_id)
    else:
        task = task_manager.get_running_task("verify_accounts")
        if not task:
            all_tasks = task_manager.get_all_tasks()
            verify_tasks = [t for t in all_tasks.values() if t.task_type == "verify_accounts"]
            if verify_tasks:
                task = max(verify_tasks, key=lambda t: t.started_at or t.completed_at)

    if task:
        return JsonResponse({
            "status": "found",
            "task": _task_to_dict(task)
        })
    else:
        return JsonResponse({
            "status": "not_found",
            "message": "No se encontró la tarea",
            "task": None
        }, status=404)


@csrf_exempt
@require_http_methods(["POST"])
def verify_accounts_debug(request):
    """
    Endpoint DEBUG para ver qué emails se están extrayendo del Excel vs BD.
    Este SÍ se ejecuta de forma síncrona porque es solo lectura y rápido.
    """

    try:
        manager = SheetsSyncManager()

        # Obtener datos del Excel
        sheets_data = manager.fetch_sheets_data()
        excel_emails = set()

        IGNORE_SHEETS = ["Vencidos", "Account name", "Spotify Premium", "YouTube Premium"]

        sheets_info = []
        for record in sheets_data:
            sheet_name = record.get("sheetName", "")

            if sheet_name in IGNORE_SHEETS:
                continue

            email = record.get("EMAIL")
            if email:
                email = email.strip().lower()
                excel_emails.add(email)

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
                "total_emails_found": len(excel_emails),
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


@csrf_exempt
@require_http_methods(["GET"])
def tasks_list(request):
    """
    Lista todas las tareas en segundo plano.
    Útil para monitoreo.
    """
    task_manager = get_task_manager()
    all_tasks = task_manager.get_all_tasks()

    tasks_list = []
    for task in all_tasks.values():
        tasks_list.append(_task_to_dict(task))

    # Ordenar por fecha de inicio (más recientes primero)
    tasks_list.sort(key=lambda t: t['started_at'] or '', reverse=True)

    return JsonResponse({
        "status": "success",
        "total_tasks": len(tasks_list),
        "tasks": tasks_list
    })
