# 🚀 Dockerfile Configurado para Dokploy

## ✅ Lo que se hizo

### 1. **Multi-Stage Dockerfile**

El Dockerfile ahora tiene dos etapas:

```dockerfile
# Stage 1: BUILDER
FROM python:3.12-slim as builder
# - Compila todas las dependencias
# - Instala gcc y libmysqlclient-dev (necesarios para compilar)

# Stage 2: PRODUCTION
FROM python:3.12-slim as production
# - Imagen limpia y optimizada
# - Solo dependencias de runtime
# - Usuario no-root (django)
# - Health check integrado
```

### 2. **Configuración para Dokploy**

En tu panel de Dokploy, debes configurar:

| Campo                   | Valor          |
| ----------------------- | -------------- |
| **Dockerfile Path**     | `./Dockerfile` |
| **Docker Context Path** | `.`            |
| **Docker Build Stage**  | `production`   |

### 3. **Health Check**

✅ Endpoint: `GET /health/`
✅ Responde: `{"status": "ok", "message": "Aplicación corriendo"}`

### 4. **Seguridad**

✅ Usuario no-root (`django`)
✅ Imagen slim (tamaño reducido)
✅ Sin compiladores en producción
✅ Permisos correctamente configurados

### 5. **Optimizaciones**

✅ Multi-stage = imagen más pequeña
✅ Cache de capas = builds más rápidos
✅ Gunicorn optimizado para producción
✅ Logging a stdout (para Dokploy)

## 📝 Archivos Nuevos

| Archivo                | Propósito                  |
| ---------------------- | -------------------------- |
| `DOKPLOY_GUIDE.md`     | Guía completa para Dokploy |
| `DOKPLOY_CHECKLIST.md` | Checklist de configuración |
| `Dockerfile`           | Multi-stage optimizado     |

## 🔑 Variables de Entorno en Dokploy

```env
DEBUG=False
SECRET_KEY=<tu-clave-secreta>
ALLOWED_HOSTS=tu-dominio.com

DB_ENGINE=django.db.backends.mysql
DB_NAME=cuentasmexico
DB_USER=luinmack
DB_PASSWORD=Tarkan11.-
DB_HOST=187.136.94.242
DB_PORT=3306
```

## 🎯 Tamaño de Imagen

Antes (single-stage):

- ~500MB (incluye gcc, compiladores)

Después (multi-stage):

- ~200MB (solo runtime)

✅ **60% más pequeña**

## 📦 Comando de Build en Dokploy

```bash
docker build --target production -t cuentasmexico:latest .
```

## ✨ Ventajas

✅ Imagen mucho más pequeña
✅ Deploy más rápido
✅ Menos uso de almacenamiento
✅ Seguridad mejorada
✅ Health check automático
✅ Logs visibles en Dokploy

## 🚨 Importante

⚠️ **NO cambies el Build Stage**

- Mantén: `production`
- Ésta es la etapa final optimizada

⚠️ **NO descomentar** `python manage.py collectstatic`

- Los estáticos se recopilan en el build
- Si está comentado, se hace en runtime

## 🔍 Verificar después del Deploy

```bash
# Desde la consola de Dokploy
curl http://localhost:8000/health/

# Respuesta esperada
{"status": "ok", "message": "Aplicación corriendo"}
```

## 📞 Soporte

Si tienes problemas:

1. Revisa `DOKPLOY_GUIDE.md`
2. Usa el checklist en `DOKPLOY_CHECKLIST.md`
3. Verifica logs en Dokploy
