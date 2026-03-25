.PHONY: build up down logs shell migrate makemigrations test superuser lint worker beat

build:
	docker compose up --build -d

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f api

logs-worker:
	docker compose logs -f celery_worker

shell:
	docker compose exec api python manage.py shell

migrate:
	docker compose exec api python manage.py migrate

makemigrations:
	docker compose exec api python manage.py makemigrations

test:
	docker compose exec api pytest

test-v:
	docker compose exec api pytest -v

test-cov:
	docker compose exec api pytest --cov=apps --cov-report=term-missing

superuser:
	docker compose exec api python manage.py createsuperuser

worker:
	celery -A config worker --loglevel=info

beat:
	celery -A config beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler

lint:
	flake8 apps/ config/ tests/

# Local dev (no Docker)
local-migrate:
	python manage.py migrate

local-run:
	python manage.py runserver

local-test:
	pytest

local-worker:
	celery -A config worker --loglevel=info

local-beat:
	celery -A config beat --loglevel=info
