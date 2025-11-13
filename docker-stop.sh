#!/bin/bash
# Script para detener los contenedores de Docker

echo "Deteniendo Cuentas México Docker..."
docker-compose down

echo "✅ Contenedores detenidos"
echo ""
echo "Para remover volúmenes y datos de la BD, ejecuta:"
echo "  docker-compose down -v"
