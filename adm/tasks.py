"""
Tareas asincrónicas con Celery para sincronización de Google Sheets.

Para usar esto, primero instala Celery:
    pip install celery redis django-celery-beat

Luego en settings.py agrega:
    CELERY_BROKER_URL = 'redis://localhost:6379'
    CELERY_RESULT_BACKEND = 'redis://localhost:6379'
    CELERY_ACCEPT_CONTENT = ['json']
    CELERY_TASK_SERIALIZER = 'json'

Y en el beat schedule:
    from celery.schedules import crontab
    
    CELERY_BEAT_SCHEDULE = {
        'sync-sheets-every-2-hours': {
            'task': 'adm.tasks.sync_sheets_task',
            'schedule': crontab(minute=0, hour='*/2'),  # Cada 2 horas
        },
    }
"""

from celery import shared_task
import logging

logger = logging.getLogger(__name__)


@shared_task
def sync_sheets_task():
    """
    Tarea Celery para sincronizar Google Sheets.
    Se ejecuta de forma asincrónica en background.
    """
    from adm.functions.sync_google_sheets import sync_google_sheets
    
    try:
        logger.info("🔄 Iniciando sincronización (tarea Celery)...")
        summary = sync_google_sheets()
        
        logger.info(f"""
✅ SINCRONIZACIÓN COMPLETADA (Celery)
  ✏️ Actualizadas: {summary['total_updated']}
  ✨ Creadas: {summary['total_created']}
  ⏸️ Suspendidas: {summary['total_suspended']}
  🔐 Cambios de contraseña: {summary['password_changes']}
  📊 Cambios de estado: {summary['status_changes']}
  ❌ Errores: {summary['total_errors']}
        """)
        
        return {
            "status": "success",
            "summary": summary
        }
    
    except Exception as e:
        logger.error(f"❌ Error en tarea Celery: {str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }


@shared_task
def check_sync_status():
    """
    Tarea para verificar el status de última sincronización.
    Útil para monitoreo.
    """
    from django.core.cache import cache
    from django.utils import timezone
    
    last_sync = cache.get('last_google_sheets_sync', None)
    
    if last_sync:
        last_sync_time = last_sync.get('timestamp')
        time_ago = timezone.now() - timezone.datetime.fromisoformat(last_sync_time)
        
        logger.info(f"📊 Última sincronización: {time_ago} ago")
        
        # Alertar si hace más de 4 horas que no se sincroniza
        if time_ago.total_seconds() > 14400:  # 4 horas
            logger.warning("⚠️ Alerta: Hace más de 4 horas que no se sincroniza")
            return {"status": "warning", "time_since_last_sync": str(time_ago)}
    
    return {"status": "ok"}
