#!/bin/bash
# Script para ejecutar comandos dentro del contenedor Django

if [ $# -eq 0 ]; then
    echo "Uso: ./docker-exec.sh <comando>"
    echo ""
    echo "Ejemplos:"
    echo "  ./docker-exec.sh python manage.py createsuperuser"
    echo "  ./docker-exec.sh python manage.py migrate"
    echo "  ./docker-exec.sh python manage.py shell"
    exit 1
fi

docker-compose exec web "$@"
