# Guía de Dockerización - Cuentas México

## 📋 Descripción General

Este proyecto ha sido dockerizado con:

- **Django** como framework web
- **MySQL** conexión a BD existente en producción
- **Nginx** como proxy inverso
- **Gunicorn** como servidor WSGI

⚠️ **IMPORTANTE**: Este Docker está configurado para conectarse a la base de datos EXISTENTE en producción. NO crea una nueva BD.

## 🚀 Inicio Rápido

### Opción 1: Producción (Recomendado)

```bash
chmod +x docker-start.sh
./docker-start.sh
```

### Opción 2: Desarrollo (usa BD de producción)

```bash
chmod +x dev-docker-start.sh
./dev-docker-start.sh
```

### Opción 3: Comandos manuales

```bash
# Copiar archivo de ambiente
cp .env.production .env

# Editar .env con tus valores si es necesario
nano .env

# Construir e iniciar
docker-compose up -d

# Recolectar estáticos
docker-compose exec web python manage.py collectstatic --noinput
```

## 📁 Estructura de Archivos

```
├── Dockerfile                 # Imagen Docker para Django
├── docker-compose.yml        # Orquestación de contenedores
├── nginx.conf               # Configuración de Nginx
├── .env.docker              # Variables de entorno de ejemplo
├── docker-start.sh          # Script para iniciar
├── docker-stop.sh           # Script para detener
├── docker-exec.sh           # Script para ejecutar comandos
└── DOCKER_GUIDE.md          # Esta guía
```

## 🐳 Contenedores

### 1. **web** (Django/Gunicorn)

- Puerto: 8000 (interno)
- No ejecuta migraciones (BD existente)
- Solo recolecta archivos estáticos
- Volumen: Código del proyecto

### 2. **nginx** (Proxy inverso)

- Puerto: 80 (HTTP)
- Puerto: 443 (HTTPS - si está configurado)
- Sirve archivos estáticos y media
- Proxy a Django

⚠️ **NO HAY servicio de MySQL en Docker** - Usa la BD existente

## 🔧 Configuración

### Variables de Entorno (.env)

```bash
# Django
DEBUG=False
SECRET_KEY=your-very-secret-key
ALLOWED_HOSTS=localhost,127.0.0.1,tu-dominio.com

# Base de datos EXISTENTE
DB_ENGINE=django.db.backends.mysql
DB_NAME=cuentasmexico
DB_USER=luinmack
DB_PASSWORD=Tarkan11.-
DB_HOST=187.136.94.242
DB_PORT=3306

# Email (Opcional)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=tu-email@gmail.com
EMAIL_HOST_PASSWORD=tu-contraseña-app
```

## 📝 Comandos Útiles

### Ejecutar migraciones (si es necesario)

```bash
docker-compose exec web python manage.py migrate
```

### Crear superusuario

```bash
docker-compose exec web python manage.py createsuperuser
```

### Acceder a MySQL (si necesitas)

```bash
# Desde otra máquina (ya que BD está en servidor externo)
mysql -h 187.136.94.242 -u luinmack -p cuentasmexico
```

### Ver logs

```bash
docker-compose logs -f web           # Logs del Django
docker-compose logs -f nginx         # Logs de Nginx
```

## 🌐 Acceso a la Aplicación

- **Aplicación**: http://localhost
- **Admin Django**: http://localhost/admin
- **API**: http://localhost/api

## 🔒 Seguridad

### En Producción

1. **Cambiar SECRET_KEY**

   ```bash
   python manage.py shell
   from django.core.management.utils import get_random_secret_key
   print(get_random_secret_key())
   ```

2. **Configurar DEBUG=False**

   ```env
   DEBUG=False
   ```

3. **Usar contraseñas fuertes**

   ```bash
   # Generar contraseña aleatoria
   openssl rand -base64 32
   ```

4. **Configurar SSL/TLS**

   - Descomenta la sección HTTPS en `nginx.conf`
   - Coloca certificados en `./ssl/`
   - Usa Let's Encrypt para certificados gratuitos

5. **Whitelist de hosts**
   ```env
   ALLOWED_HOSTS=cuentasmexico.mx,www.cuentasmexico.mx
   ```

## 🛠️ Troubleshooting

### Problema: Error de conexión a BD

**Solución**: Verifica que los datos de conexión en `.env` sean correctos

```bash
DB_HOST=187.136.94.242
DB_USER=luinmack
DB_PASSWORD=Tarkan11.-
DB_NAME=cuentasmexico
DB_PORT=3306
```

### Problema: Puertos en uso

**Solución**: Cambia los puertos en `docker-compose.yml`

```yaml
ports:
  - '8001:8000' # Cambiar puerto externo
```

### Problema: Permisos de archivos

**Solución**: Ajusta permisos

```bash
sudo chmod 755 docker-*.sh dev-docker-start.sh
```

### Problema: Archivos estáticos no cargan

**Solución**: Recolectar estáticos

```bash
docker-compose exec web python manage.py collectstatic --noinput
docker-compose restart nginx
```

### Ver todos los contenedores

```bash
docker ps -a
```

### Ver logs detallados

```bash
docker-compose logs -f web
```

## 📚 Recursos Útiles

- [Documentación de Docker](https://docs.docker.com/)
- [Documentación de Docker Compose](https://docs.docker.com/compose/)
- [Documentación de Django](https://docs.djangoproject.com/)
- [Documentación de Nginx](https://nginx.org/en/docs/)
- [MySQL Docker Official Image](https://hub.docker.com/_/mysql)

## 📞 Soporte

Para problemas específicos, consulta:

1. Los logs: `docker-compose logs`
2. La documentación oficial de cada servicio
3. La documentación del proyecto

## 📄 Licencia

Este proyecto se dockerizó como parte de Cuentas México.
