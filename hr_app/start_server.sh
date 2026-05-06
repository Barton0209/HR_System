#!/bin/bash
# HR System - Script запуска сервера для локальной сети

echo "=========================================="
echo "  HR System v2.0 - Запуск сервера"
echo "=========================================="
echo ""

# Переход в директорию проекта
cd "$(dirname "$0")/.."

# Проверка Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Ошибка: Python3 не найден!"
    exit 1
fi

echo "✅ Python3: $(python3 --version)"

# Проверка и установка зависимостей
echo ""
echo "📦 Проверка зависимостей..."
pip3 install -q -r hr_app/requirements.txt 2>/dev/null || {
    echo "⚠️ Предупреждение: некоторые пакеты могут не установиться"
}

# Получение IP адреса для доступа из локальной сети
LOCAL_IP=$(hostname -I | awk '{print $1}')
PORT=8000

echo ""
echo "=========================================="
echo "  🚀 Запуск сервера..."
echo "=========================================="
echo ""
echo "  Локальный доступ: http://localhost:${PORT}"
echo "  Доступ из сети:   http://${LOCAL_IP}:${PORT}"
echo ""
echo "  Для остановки нажмите: Ctrl+C"
echo ""
echo "=========================================="
echo ""

# Запуск сервера
exec python3 -m uvicorn hr_app.backend.main:app \
    --host 0.0.0.0 \
    --port ${PORT} \
    --reload
