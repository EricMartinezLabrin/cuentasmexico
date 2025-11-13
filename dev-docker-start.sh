#!/bin/bash
# Script para iniciar Docker en modo DESARROLLO
# Conecta a la BD EXISTENTE en producción

set -e

echo "================================"
echo "Iniciando en MODO DESARROLLO"
echo "CONECTANDO A BD DE PRODUCCIÓN"
echo "================================"
echo ""

# Construir imagen
echo "🔨 Construyendo imagen Docker..."
docker-compose -f docker-compose.dev.yml build

# Iniciar contenedores
echo "🚀 Iniciando contenedores..."
docker-compose -f docker-compose.dev.yml up -d

# Esperar a que la aplicación esté lista
echo "⏳ Esperando a que la aplicación esté lista..."
sleep 5

echo ""
echo "================================"
echo "✅ Servidor de desarrollo corriendo"
echo "================================"
echo ""
echo "URLs disponibles:"
echo "  • Aplicación: http://localhost:8000"
echo "  • Admin: http://localhost:8000/admin"
echo ""
echo "Para ver logs en vivo:"
echo "  docker-compose -f docker-compose.dev.yml logs -f web"
echo ""
echo "Para ejecutar comandos:"
echo "  docker-compose -f docker-compose.dev.yml exec web <comando>"
echo ""
echo "Para detener:"
echo "  docker-compose -f docker-compose.dev.yml down"
echo ""
