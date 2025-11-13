# ✅ Checklist para Dokploy Deployment

## 📋 Requisitos Previos

- [ ] Cuenta en Dokploy
- [ ] Repositorio GitHub conectado
- [ ] Variables de entorno preparadas

## 🔧 Configuración en Dokploy

### Paso 1: Docker Build

```
Dockerfile Path:        ./Dockerfile
Docker Context Path:    .
Docker Build Stage:     production
```

### Paso 2: Variables de Entorno

```env
DEBUG=False
SECRET_KEY=<generar-clave-segura>
ALLOWED_HOSTS=tu-dominio.com,www.tu-dominio.com

DB_ENGINE=django.db.backends.mysql
DB_NAME=cuentasmexico
DB_USER=luinmack
DB_PASSWORD=Tarkan11.-
DB_HOST=187.136.94.242
DB_PORT=3306

N8N_WEBHOOK_URL_CHANGE_PASSWORD=https://n8n.fadetechs.com/webhook/7145fd4e-9f73-44e2-b733-8a18fb2bb377
IFRAME_ACCESS_TOKEN=7145fd4e-9f73-44e2-b733-8a18fb2bb377
```

### Paso 3: Puerto

```
Port: 8000
```

### Paso 4: Health Check (Recomendado)

```
Enabled:    ✓
Path:       /health/
Protocol:   HTTP
Interval:   30s
Timeout:    10s
Start Period: 40s
Retries:    3
```

## 🚀 Deploy

1. **Push** cambios a GitHub
2. **Dokploy** detecta cambios automáticamente
3. **Build** comienza (3-5 min)
4. **Deploy** se activa si todo sale bien

## 📊 Monitoreo

Ver logs en tiempo real:

```bash
# Desde la consola de Dokploy
docker logs -f <container-name>
```

## 🆘 Troubleshooting

| Problema            | Solución                         |
| ------------------- | -------------------------------- |
| Build falla         | Revisa logs, verifica SECRET_KEY |
| Health check falla  | Espera 60s, aumenta timeout      |
| BD no conecta       | Verifica IP/puerto desde Dokploy |
| Estáticos no cargan | Agrega proxy inverso (Nginx)     |

## 📝 Comandos Útiles en Dokploy

```bash
# Ejecutar comando en contenedor
docker exec <container> python manage.py <comando>

# Migraciones (si es necesario)
docker exec <container> python manage.py migrate

# Ver variables
docker inspect <container> | grep Env
```

## ✨ Características Activadas

✅ Multi-stage Dockerfile (optimizado)
✅ Usuario no-root (seguridad)
✅ Health check endpoint
✅ Gunicorn configurado
✅ Logging a stdout
✅ BD externa (sin Docker)

## 📞 Soporte

- [Dokploy Discord](https://discord.gg/dokploy)
- Email: support@dokploy.com
- Docs: https://dokploy.com/docs
