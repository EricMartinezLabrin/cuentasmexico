# ⚠️ IMPORTANTE: Cambios en la Configuración Docker

## ✅ Lo que cambió

### 1. **Servicio MySQL Removido**

- ❌ Ya NO se crea una nueva BD en Docker
- ✅ Se conecta a la BD EXISTENTE en `187.136.94.242`

### 2. **Migraciones Deshabilitadas**

- ❌ Docker NO ejecuta `python manage.py migrate`
- ✅ Solo ejecuta `collectstatic` para archivos estáticos
- ℹ️ Si necesitas migrar, ejecuta manualmente: `docker-compose exec web python manage.py migrate`

### 3. **Base de Datos Configurada**

Los valores en `.env` apuntan a tu BD en producción:

```
DB_HOST=187.136.94.242
DB_USER=luinmack
DB_PASSWORD=Tarkan11.-
DB_NAME=cuentasmexico
DB_PORT=3306
```

## 🚀 Cómo Usar

### Opción 1: Producción (con Nginx)

```bash
./docker-start.sh
```

- Accede a: http://localhost
- Admin: http://localhost/admin

### Opción 2: Desarrollo (sin Nginx, solo Django)

```bash
./dev-docker-start.sh
```

- Accede a: http://localhost:8000
- Admin: http://localhost:8000/admin

## 📝 Archivos Importantes

| Archivo                  | Propósito                |
| ------------------------ | ------------------------ |
| `.env.production`        | Variables de producción  |
| `.env.docker`            | Variables de ejemplo     |
| `docker-compose.yml`     | Producción (web + nginx) |
| `docker-compose.dev.yml` | Desarrollo (solo web)    |
| `docker-start.sh`        | Script para producción   |
| `dev-docker-start.sh`    | Script para desarrollo   |

## ⚠️ Si necesitas ejecutar migraciones

```bash
# Conectarse al contenedor
docker-compose exec web python manage.py migrate
```

## ℹ️ Notas Importantes

1. ✅ La aplicación usa la BD existente (sin riesgo de datos)
2. ✅ Nginx sirve archivos estáticos rápidamente
3. ✅ Gunicorn maneja las peticiones de Django
4. ✅ Los cambios de código se actualizan automáticamente en desarrollo
5. ⚠️ En producción, es necesario reiniciar el contenedor para cambios

## 🔧 Comandos Útiles

```bash
# Ver logs
docker-compose logs -f web

# Ejecutar comando personalizado
docker-compose exec web python manage.py shell

# Recolectar estáticos nuevamente
docker-compose exec web python manage.py collectstatic --noinput

# Reiniciar
docker-compose restart

# Detener
docker-compose down
```

## 📞 Soporte

Si tienes problemas:

1. Verifica que `.env` tenga los datos correctos
2. Revisa los logs: `docker-compose logs -f`
3. Asegúrate que la BD sea accesible desde Docker
