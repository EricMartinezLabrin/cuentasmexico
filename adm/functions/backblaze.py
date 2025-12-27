# Backblaze B2 Integration via S3 Compatible API
# Usa django-storages con boto3 para una conexión mucho más rápida y estable

import logging
from datetime import datetime
from urllib.parse import quote

from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage

logger = logging.getLogger(__name__)


class BackblazeS3Storage(S3Boto3Storage):
    """
    Storage backend para Backblaze B2 usando la API compatible con S3.
    Extiende S3Boto3Storage de django-storages para manejar archivos antiguos locales.
    """
    
    # Prefijos de archivos que están guardados localmente (antes de Backblaze)
    LOCAL_PREFIXES = ['settings/', 'bank/', 'users/']
    
    def __init__(self, *args, **kwargs):
        # Configuración para Backblaze B2
        kwargs.setdefault('access_key', settings.AWS_ACCESS_KEY_ID)
        kwargs.setdefault('secret_key', settings.AWS_SECRET_ACCESS_KEY)
        kwargs.setdefault('bucket_name', settings.AWS_STORAGE_BUCKET_NAME)
        kwargs.setdefault('endpoint_url', settings.AWS_S3_ENDPOINT_URL)
        kwargs.setdefault('region_name', settings.AWS_S3_REGION_NAME)
        kwargs.setdefault('custom_domain', getattr(settings, 'AWS_S3_CUSTOM_DOMAIN', None))
        kwargs.setdefault('file_overwrite', False)
        kwargs.setdefault('default_acl', 'public-read')
        kwargs.setdefault('querystring_auth', False)  # URLs públicas sin firma
        
        super().__init__(*args, **kwargs)
        logger.info("BackblazeS3Storage inicializado")
    
    def _is_local_file(self, name):
        """
        Verifica si el archivo es uno local antiguo (sin timestamp).
        Los archivos nuevos tienen timestamp (ej: users/20251227_142647_...) y están en B2.
        Los archivos antiguos no tienen timestamp (ej: users/foto.jpg) y están locales.
        """
        if not name:
            return False
        
        # Si comienza con algún prefijo local
        if not any(name.startswith(prefix) for prefix in self.LOCAL_PREFIXES):
            return False
        
        # Archivos con timestamp (YYYYMMDD_HHMMSS_) están en B2, no son locales
        import re
        has_timestamp = re.search(r'/\d{8}_\d{6}_', name)
        if has_timestamp:
            return False  # Es un archivo nuevo con timestamp, está en B2
        
        # Si no tiene timestamp, es un archivo local antiguo
        return True
    
    def _save(self, name, content):
        """
        Guarda el archivo en Backblaze B2.
        Genera un nombre único con timestamp.
        """
        try:
            # Determinar la carpeta en B2
            if 'settings' in name or 'logo' in name.lower():
                b2_folder = 'services'
            elif 'bank' in name:
                b2_folder = 'bank'
            elif 'users' in name:
                b2_folder = 'users'
            else:
                b2_folder = 'files'
            
            # Generar nombre único
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            original_name = name.split('/')[-1] if '/' in name else name
            new_name = f"{b2_folder}/{timestamp}_{original_name}"
            
            logger.info(f"[BackblazeS3] Guardando: {new_name}")
            
            # Llamar al método padre para guardar en S3
            saved_name = super()._save(new_name, content)
            
            logger.info(f"[BackblazeS3] Guardado exitosamente: {saved_name}")
            return saved_name
            
        except Exception as e:
            logger.error(f"[BackblazeS3] Error al guardar: {str(e)}", exc_info=True)
            raise
    
    def url(self, name):
        """
        Retorna la URL del archivo.
        Para archivos locales antiguos, retorna /media/...
        Para archivos en B2, retorna la URL de Backblaze.
        """
        if not name:
            return None
        
        # Si ya es una URL completa, retornarla
        if name.startswith('http'):
            return name
        
        # Archivos locales antiguos
        if self._is_local_file(name):
            return f"/media/{name}"
        
        # URL encode del nombre (preservando /)
        encoded_name = quote(name, safe='/')
        
        # Usar custom_domain si está configurado
        if self.custom_domain:
            return f"https://{self.custom_domain}/{encoded_name}"
        
        # Fallback a URL de S3
        try:
            return super().url(name)
        except Exception as e:
            logger.error(f"[BackblazeS3] Error generando URL: {str(e)}")
            return f"{settings.AWS_S3_ENDPOINT_URL}/{settings.AWS_STORAGE_BUCKET_NAME}/{encoded_name}"
    
    def exists(self, name):
        """Verifica si el archivo existe"""
        if not name:
            return False
        
        # Para archivos locales, asumir que no existen en S3
        if self._is_local_file(name):
            return False
        
        try:
            return super().exists(name)
        except Exception:
            return False
    
    def delete(self, name):
        """Elimina un archivo de Backblaze B2"""
        if not name or self._is_local_file(name):
            return
        
        try:
            super().delete(name)
            logger.info(f"[BackblazeS3] Archivo eliminado: {name}")
        except Exception as e:
            logger.error(f"[BackblazeS3] Error al eliminar: {str(e)}")


# Alias para compatibilidad con código existente
HybridBackblazeStorage = BackblazeS3Storage
BackblazeStorage = BackblazeS3Storage


class BackblazeManager:
    """
    Clase legacy para compatibilidad con código existente.
    Ahora usa boto3 internamente.
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BackblazeManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        self._storage = None
    
    @property
    def storage(self):
        if self._storage is None:
            self._storage = BackblazeS3Storage()
        return self._storage
    
    def upload_image(self, uploaded_file, folder='services'):
        """Método legacy para subir imágenes"""
        try:
            if not uploaded_file:
                return None
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            file_name = f"{folder}/{timestamp}_{uploaded_file.name}"
            
            saved_name = self.storage.save(file_name, uploaded_file)
            return self.storage.url(saved_name)
            
        except Exception as e:
            logger.error(f"Error al subir imagen: {str(e)}")
            return None
    
    def delete_image(self, image_url):
        """Método legacy para eliminar imágenes"""
        try:
            if not image_url:
                return True
            
            # Extraer nombre del archivo de la URL
            if '/' in image_url:
                name = '/'.join(image_url.split('/')[-2:])
                self.storage.delete(name)
            
            return True
        except Exception as e:
            logger.error(f"Error al eliminar imagen: {str(e)}")
            return False
    
    def get_image_url(self, image_url):
        """Método legacy para obtener URL"""
        return image_url if image_url else None


def get_backblaze_manager():
    """Factory function para obtener la instancia del manager"""
    return BackblazeManager()

