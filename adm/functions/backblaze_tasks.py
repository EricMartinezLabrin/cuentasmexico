# Tasks asincrónicas para Backblaze B2
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

# Intentar importar Celery (opcional)
try:
    from celery import shared_task
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False
    # Crear un decorador dummy si Celery no está disponible
    def shared_task(*args, **kwargs):
        """Decorador dummy que simplemente retorna la función sin modificar"""
        def decorator(func):
            return func
        # Si se usa como @shared_task sin paréntesis
        if len(args) == 1 and callable(args[0]):
            return args[0]
        return decorator


def upload_to_backblaze_async(file_path, b2_filename, folder='files'):
    """
    Tarea para subir un archivo a Backblaze B2.
    Solo funciona como tarea asincrónica si Celery está disponible.
    
    Args:
        file_path: Ruta local del archivo temporal
        b2_filename: Nombre con el que se guardará en B2
        folder: Carpeta en B2
    """
    try:
        from adm.functions.backblaze import get_backblaze_manager
        
        logger.info(f"Iniciando carga de {file_path} a B2 como {b2_filename}")
        
        # Leer el archivo local
        with open(file_path, 'rb') as f:
            file_content = f.read()
        
        # Obtener el manager de Backblaze
        manager = get_backblaze_manager()
        
        # Subir a B2
        file_info = manager.bucket.upload_bytes(
            data_bytes=file_content,
            file_name=b2_filename,
            content_type='application/octet-stream'
        )
        
        logger.info(f"Archivo cargado exitosamente a Backblaze: {b2_filename}")
        
        # Eliminar el archivo temporal
        try:
            os.remove(file_path)
            logger.info(f"Archivo temporal eliminado: {file_path}")
        except Exception as e:
            logger.warning(f"No se pudo eliminar archivo temporal {file_path}: {str(e)}")
        
        return {'status': 'success', 'file': b2_filename}
    
    except Exception as e:
        logger.error(f"Error en carga de {b2_filename}: {str(e)}", exc_info=True)
        raise


# Si Celery está disponible, decorar la función
if CELERY_AVAILABLE:
    upload_to_backblaze_async = shared_task(
        bind=True, 
        max_retries=3
    )(upload_to_backblaze_async)
