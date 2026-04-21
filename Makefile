# Makefile — IDPS + Ticket App

.PHONY: install run-ticket run-api db-init db-reset up down logs clean

# Установка зависимостей
install:
	pip install -r requirements.txt

# Запуск Ticket App (GUI)
run-ticket:
	cd ticket_app && python main.py

# Запуск всех API сервисов локально
run-ocr:
	cd ocr_core && uvicorn main:app --host 0.0.0.0 --port 8001 --reload

run-nlp:
	cd nlp_layer && uvicorn main:app --host 0.0.0.0 --port 8002 --reload

run-ingestor:
	cd ingestor && uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Docker Compose
up:
	docker-compose up -d

down:
	docker-compose down --remove-orphans

logs:
	docker-compose logs -f

build:
	docker-compose build --no-cache

# База данных
db-init:
	docker-compose exec -T postgres psql -U idps -d idps -f /docker-entrypoint-initdb.d/schema.sql
	docker-compose exec -T postgres psql -U idps -d idps -f /docker-entrypoint-initdb.d/seed.sql

db-reset:
	docker-compose exec -T postgres psql -U idps -d idps -c "DROP SCHEMA idps CASCADE; CREATE SCHEMA idps;"
	$(MAKE) db-init

# Очистка
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	rm -f ticket_app/employees_database.json
	rm -f ticket_app/ticket_app.log
