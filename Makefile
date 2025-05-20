.PHONY: build up down logs shell static migrate makemigrations createsuperuser help restart terminal

help:
	@echo "Available commands:"
	@echo "  make build         - Build Docker images"
	@echo "  make up           - Start the application"
	@echo "  make down         - Stop the application"
	@echo "  make restart      - Restart the application"
	@echo "  make logs         - View application logs"
	@echo "  make shell        - Open Django shell"
	@echo "  make static       - Collect static files"
	@echo "  make migrate      - Run database migrations"
	@echo "  make makemigrations - Create new migrations"
	@echo "  make createsuperuser - Create a superuser"
	@echo "  make terminal     - Open a shell inside the web container"

build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

shell:
	docker-compose exec web python manage.py shell

static:
	docker-compose exec web python manage.py collectstatic --noinput

migrate:
	docker-compose exec web python manage.py migrate

makemigrations:
	docker-compose exec web python manage.py makemigrations

createsuperuser:
	docker-compose exec web python manage.py createsuperuser 

restart: down up

terminal:
	docker-compose exec web /bin/bash

