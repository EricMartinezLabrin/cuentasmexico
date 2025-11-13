# Makefile para facilitar comandos Docker

.PHONY: help build up down logs shell migrate createsuperuser clean restart

help:
	@echo "Comandos disponibles:"
	@echo "  make build              - Construir imagen Docker"
	@echo "  make up                 - Iniciar contenedores"
	@echo "  make down               - Detener contenedores"
	@echo "  make dev-up             - Iniciar en modo desarrollo"
	@echo "  make dev-down           - Detener modo desarrollo"
	@echo "  make logs               - Ver logs del web"
	@echo "  make shell              - Entrar a shell de Django"
	@echo "  make migrate            - Ejecutar migraciones"
	@echo "  make createsuperuser    - Crear superusuario"
	@echo "  make collectstatic      - Recolectar archivos estáticos"
	@echo "  make restart            - Reiniciar contenedores"
	@echo "  make clean              - Limpiar contenedores y volúmenes"

build:
	docker-compose build

up:
	docker-compose up -d
	@echo "✅ Contenedores iniciados"

down:
	docker-compose down
	@echo "✅ Contenedores detenidos"

dev-up:
	chmod +x dev-docker-start.sh
	./dev-docker-start.sh

dev-down:
	docker-compose -f docker-compose.dev.yml down
	@echo "✅ Modo desarrollo detenido"

logs:
	docker-compose logs -f web

shell:
	docker-compose exec web python manage.py shell

migrate:
	docker-compose exec web python manage.py migrate

createsuperuser:
	docker-compose exec web python manage.py createsuperuser

collectstatic:
	docker-compose exec web python manage.py collectstatic --noinput

restart:
	docker-compose restart web

clean:
	docker-compose down -v
	@echo "✅ Contenedores y volúmenes eliminados"

dbshell:
	docker-compose exec db mysql -u cuentas -p cuentasmexico
