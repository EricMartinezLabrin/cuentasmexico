#!/bin/bash
# Script para limpiar y reparar permisos de Docker

echo "🧹 Limpiando contenedores y volúmenes..."

# Detener contenedores
docker-compose down

# Remover volúmenes
docker volume rm cuentasmexico_static_volume cuentasmexico_media_volume 2>/dev/null || true

echo "✅ Volúmenes limpiados"
echo ""

# Opcionalmente remover imagen
read -p "¿Remover imagen Docker? (s/n): " remove_image
if [ "$remove_image" = "s" ] || [ "$remove_image" = "S" ]; then
    docker rmi cuentasmexico_web 2>/dev/null || true
    echo "✅ Imagen removida"
fi

echo ""
echo "🚀 Iniciando nuevamente..."
docker-compose up -d

echo ""
echo "✅ Contenedores iniciados"
echo ""
echo "Ver logs:"
echo "  docker-compose logs -f web"
