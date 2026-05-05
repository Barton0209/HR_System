#!/bin/bash
# Скрипт запуска HR System сервера
cd "$(dirname "$0")/.."
echo "🚀 Запуск HR System v2.0..."
echo "📍 Откройте в браузере: http://localhost:8000"
echo "📊 Swagger API документация: http://localhost:8000/docs"
echo ""
uvicorn hr_app.backend.main:app --host 0.0.0.0 --port 8000 --reload
