#!/bin/bash
# Script para iniciar los contenedores de Docker - PRODUCCIÓN

set -e

echo "================================"
echo "Iniciando Cuentas México Docker"
echo "CONECTANDO A BD EXISTENTE"
echo "================================"

# Copiar archivo .env si no existe
if [ ! -f .env ]; then
    echo "Creando archivo .env desde .env.production..."
    cp .env.production .env
    echo "⚠️  Por favor, verifica que los datos de conexión en .env sean correctos"
    read -p "Presiona Enter para continuar..."
fi

# Construir imagen
echo "Construyendo imagen Docker..."
docker-compose build

# Iniciar contenedores
echo "Iniciando contenedores..."
docker-compose up -d

# Esperar a que la aplicación esté lista
echo "Esperando a que la aplicación esté lista..."
sleep 5

# Recolectar estáticos
echo "Recolectando archivos estáticos..."
docker-compose exec -T web python manage.py collectstatic --noinput

echo ""
echo "================================"
echo "✅ Cuentas México está corriendo"
echo "================================"
echo ""
echo "URLs disponibles:"
echo "  • Aplicación: http://localhost"
echo "  • Admin: http://localhost/admin"
echo "  • API: http://localhost/api"
echo ""
echo "Comandos útiles:"
echo "  • Ver logs: docker-compose logs -f web"
echo "  • Ver logs nginx: docker-compose logs -f nginx"
echo "  • Ejecutar comando: docker-compose exec web <comando>"
echo "  • Detener: docker-compose down"
echo "  • Reiniciar: docker-compose restart"
echo ""
