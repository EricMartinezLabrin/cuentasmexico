# Dokploy Configuration

# Estructura para desplegar en Dokploy

## 📋 Configuración para Dokploy

Este proyecto está configurado para desplegarse en **Dokploy** usando el Dockerfile multi-stage.

### 🚀 Pasos para desplegar en Dokploy

#### 1. **Crear nuevo Proyecto en Dokploy**

- Ve a tu dashboard de Dokploy
- Click en "Nuevo Proyecto"
- Conecta tu repositorio de GitHub

#### 2. **Configurar la Aplicación**

**Docker Settings:**

- **Dockerfile Path**: `./Dockerfile`
- **Docker Context Path**: `.`
- **Docker Build Stage**: `production`

#### 3. **Variables de Entorno**

Configura estas variables en Dokploy:

```env
# Django
DEBUG=False
SECRET_KEY=tu-clave-secreta-muy-segura
ALLOWED_HOSTS=tu-dominio.com,www.tu-dominio.com

# Database (BD Existente)
DB_ENGINE=django.db.backends.mysql
DB_NAME=cuentasmexico
DB_USER=luinmack
DB_PASSWORD=Tarkan11.-
DB_HOST=187.136.94.242
DB_PORT=3306

# Business Config
N8N_WEBHOOK_URL_CHANGE_PASSWORD=https://n8n.fadetechs.com/webhook/...
IFRAME_ACCESS_TOKEN=7145fd4e-9f73-44e2-b733-8a18fb2bb377

# Email (opcional)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=tu-email@gmail.com
EMAIL_HOST_PASSWORD=tu-contraseña-app

# API Keys (opcional)
STRIPE_SECRET_KEY=sk_live_...
STRIPE_PUBLISHABLE_KEY=pk_live_...
MERCADOPAGO_ACCESS_TOKEN=...
```

#### 4. **Puertos**

- Puerto: **8000** (Django/Gunicorn)

#### 5. **Health Check (opcional pero recomendado)**

- Endpoint: `http://localhost:8000/health/`
- Intervalo: 30s
- Timeout: 10s
- Retries: 3

#### 6. **Comandos de Build**

Si Dokploy lo permite, agrega comando personalizado:

```bash
python manage.py collectstatic --noinput
```

## 📦 Características del Dockerfile

### Multi-Stage Build

- **Builder Stage**: Compila todas las dependencias de Python
- **Production Stage**: Imagen optimizada solo con lo necesario

### Optimizaciones de Seguridad

✅ Usuario no-root (`django`)
✅ Imagen slim para reducir tamaño
✅ Sin compiladores en producción
✅ Permisos correctamente configurados

### Optimizaciones de Rendimiento

✅ Capas bien organizadas para cache
✅ Health check integrado
✅ Gunicorn configurado para producción
✅ Logging a stdout/stderr

## 🔄 Flujo de Deploy

1. **Push a GitHub** → Dokploy detecta cambios
2. **Build** → Construye usando stage `production`
3. **Test** → Health check verifica que esté corriendo
4. **Deploy** → Replica contenedor con variables de entorno

## 📝 Notas Importantes

⚠️ **No se crean migraciones automáticas** en el Dockerfile

- La BD es existente
- Si necesitas migrar manualmente:
  ```bash
  docker exec <container-id> python manage.py migrate
  ```

✅ **Archivos estáticos**

- Se recolectan en la etapa de build
- Servidos por Nginx (si está configurado)
- O por Django en desarrollo

✅ **Base de datos**

- Conecta a BD externa (187.136.94.242)
- No incluye MySQL en Docker

## 🚨 Troubleshooting

**Si el deploy falla:**

1. Verifica variables de entorno en Dokploy
2. Revisa que DB_HOST sea accesible desde Dokploy
3. Chequea los logs: `docker logs <container-id>`
4. Asegúrate que `SECRET_KEY` es única

**Si falla health check:**

- La aplicación necesita 40s para iniciarse
- Aumenta el `start-period` si es necesario

## 📞 Recursos

- [Documentación Dokploy](https://dokploy.com/docs)
- [Guía Django + Gunicorn](https://docs.gunicorn.org/)
- [Multi-stage Docker](https://docs.docker.com/build/building/multi-stage/)
