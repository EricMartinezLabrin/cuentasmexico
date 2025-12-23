# Integración de Backblaze B2

Este proyecto está configurado para almacenar todas las imágenes en **Backblaze B2** automáticamente, sin guardar ningún archivo localmente.

## Características

✅ Almacenamiento automático en Backblaze B2 para:
- Logos de servicios (Services CRUD)
- Logos de negocios (Business settings)
- Logos de bancos (Bank CRUD)
- Fotos de perfil de usuarios (UserDetail)

✅ **Sin cambios en la base de datos** - Los campos de FileField se mantienen igual
✅ **Storage backend transparente** - Django automáticamente usa Backblaze
✅ **Gestión automática de archivos** - Subida, descarga y eliminación

## Configuración

### 1. Instalar dependencias

```bash
pip install -r requirements.txt
```

Las nuevas librerías agregadas son:
- `b2sdk==2.2.0` - SDK oficial de Backblaze B2
- `Pillow==10.1.0` - Procesamiento de imágenes

### 2. Configurar variables de entorno

Crear o editar el archivo `.env` en la raíz del proyecto:

```env
BACKBLAZE_KEY_ID=tu_key_id_aqui
BACKBLAZE_APP_KEY=tu_app_key_aqui
BACKBLAZE_BUCKET_NAME=nombre_de_tu_bucket
BACKBLAZE_BUCKET_URL=https://tu_bucket_url.backblazeb2.com
```

### 3. Obtener credenciales de Backblaze B2

1. Crear cuenta en [backblaze.com](https://www.backblaze.com/b2/cloud-storage.html)
2. Ir a **Account** → **Application Keys**
3. Crear una nueva Application Key con acceso a tu bucket
4. Copiar:
   - **Application Key ID** → `BACKBLAZE_KEY_ID`
   - **Application Key** → `BACKBLAZE_APP_KEY`
5. El nombre del bucket y URL se obtienen en **Buckets** → Seleccionar tu bucket

## Cómo funciona

### Storage Backend Híbrido

Se creó una clase personalizada `HybridBackblazeStorage` en `adm/functions/backblaze.py` que:

1. **Guarda localmente primero** (instantáneo): El archivo se guarda en el servidor Django
2. **Sube a Backblaze en background** (asincrónico si Celery está disponible)
3. **Mantiene compatibilidad**: Django sigue guardando la ruta en la BD

Esto significa que el usuario **no espera** a que se suba a B2. El formulario se guarda inmediatamente.

#### Flujo sin Celery (almacenamiento local como fallback)
```
Usuario sube imagen
    ↓
Se guarda localmente (rápido - ~100ms)
    ↓
Se retorna la respuesta al usuario
    ↓
Se sube a B2 en el mismo request (background)
    ↓
La imagen está disponible desde cualquier lugar
```

#### Flujo con Celery (recomendado para producción)
```
Usuario sube imagen
    ↓
Se guarda localmente (rápido - ~100ms)
    ↓
Se programa tarea asincrónica a Celery
    ↓
Se retorna la respuesta al usuario INMEDIATAMENTE
    ↓
Celery sube a B2 en background
    ↓
Se elimina archivo local después de subir
    ↓
La imagen está disponible desde cualquier lugar
```

## Uso en plantillas

Las plantillas pueden usar las imágenes como siempre:

```html
{% if objeto.logo %}
    <img src="{{ objeto.logo }}" alt="Logo">
{% endif %}
```

Django automáticamente sirve la URL desde Backblaze.

## API del Manager

Para uso avanzado, puedes usar `BackblazeManager` directamente:

```python
from adm.functions.backblaze import get_backblaze_manager

manager = get_backblaze_manager()

# Subir imagen
url = manager.upload_image(file, folder='services')

# Eliminar imagen
manager.delete_image(url)

# Validar URL
valid_url = manager.get_image_url(url)
```

## Fallback a almacenamiento local

Si las credenciales de Backblaze no están configuradas, el sistema **automáticamente usa almacenamiento local** como fallback. Esto es útil para desarrollo.

```python
# En settings.py
if all([BACKBLAZE_KEY_ID, BACKBLAZE_APP_KEY, BACKBLAZE_BUCKET_NAME, BACKBLAZE_BUCKET_URL]):
    DEFAULT_FILE_STORAGE = 'adm.functions.backblaze.HybridBackblazeStorage'
# Si no está configurado, usa el almacenamiento por defecto de Django
```

## Celery (Opcional pero recomendado)

Para **mejor experiencia UX**, instala Celery:

```bash
pip install celery redis
```

Luego configura en `settings.py`:

```python
# Celery Configuration
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'America/Mexico_City'
```

Con Celery:
- ✅ El formulario se guarda **inmediatamente**
- ✅ La subida a B2 ocurre en background
- ✅ Si falla la subida, reintentar automáticamente
- ✅ Mejor rendimiento para muchos usuarios simultáneos

Sin Celery:
- ✅ Funciona de todas formas (sincrónico)
- ⚠️ El usuario espera a que se suba a B2
- ℹ️ Recomendado solo para desarrollo

## Estructura de carpetas en Backblaze

Las imágenes se organizan automáticamente en carpetas:

```
bucket/
├── business/          # Logos de negocios
├── services/          # Logos de servicios
├── bank/              # Logos de bancos
├── users/             # Fotos de perfil
└── files/             # Otros archivos
```

## Migraciones

⚠️ **Importante**: No se requieren migraciones de base de datos. Los campos FileField existentes se mantienen sin cambios.

Si al ejecutar el proyecto ves mensajes de advertencia sobre Backblaze, simplemente configura las variables de entorno.

## Monitoreo y logs

Los logs de Backblaze se registran en:

```python
import logging
logger = logging.getLogger(__name__)  # Para adm.functions.backblaze
```

Puedes habilitar debug en Django para ver más detalles:

```python
# En settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'adm.functions.backblaze': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}
```

## Notas de seguridad

1. **Nunca commits las credenciales**: Usa `.env` (en .gitignore) para credenciales
2. **Bucket privado**: Asegúrate que el bucket de Backblaze esté configurado como privado
3. **URLs firmadas**: Para más seguridad, puedes usar URLs firmadas en lugar de públicas
4. **Logs de acceso**: Habilita logs en Backblaze para auditar accesos

## Solución de problemas

### Error: "Credenciales inválidas"
- Verifica que BACKBLAZE_KEY_ID y BACKBLAZE_APP_KEY sean correctos
- Revisa que la Application Key no haya expirado
- Confirma que la Key tiene permisos en el bucket

### Error: "Bucket no encontrado"
- Verifica que BACKBLAZE_BUCKET_NAME sea exacto (case-sensitive)
- Asegúrate que el bucket exista en tu cuenta

### Las imágenes no aparecen
- Confirma que BACKBLAZE_BUCKET_URL es correcto
- Verifica que el bucket permita acceso público a los archivos
- Revisa los logs de Django para más detalles

## Referencias

- [Documentación de Backblaze B2](https://www.backblaze.com/b2/docs/)
- [B2SDK Python](https://pypi.org/project/b2sdk/)
- [Almacenamiento personalizado en Django](https://docs.djangoproject.com/en/4.2/howto/custom-file-storage/)
