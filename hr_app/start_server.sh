#!/bin/bash
# HR System v2.0 - Script запуска сервера для локальной сети
# Запуск без root прав, доступ по локальной сети

echo "=========================================="
echo "  HR System v2.0 - Запуск сервера"
echo "=========================================="
echo ""

# Переход в директорию проекта
cd "$(dirname "$0")"
PROJECT_ROOT="$(pwd)"

# Проверка Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Ошибка: Python3 не найден!"
    exit 1
fi

echo "✅ Python3: $(python3 --version)"

# Установка PYTHONPATH для корректного импорта модулей
export PYTHONPATH="${PROJECT_ROOT}/.."

echo "📁 Project root: ${PROJECT_ROOT}"
echo "🔧 PYTHONPATH: ${PYTHONPATH}"

# Проверка и установка зависимостей
echo ""
echo "📦 Проверка зависимостей..."
pip3 install -q -r "${PROJECT_ROOT}/requirements.txt" 2>/dev/null || {
    echo "⚠️ Предупреждение: некоторые пакеты могут не установиться"
}

# Создание необходимых директорий
mkdir -p "${PROJECT_ROOT}/data/uploads"
mkdir -p "${PROJECT_ROOT}/data/reports"
mkdir -p "${PROJECT_ROOT}/data/excel_files"

# Получение IP адреса для доступа из локальной сети
LOCAL_IP=$(hostname -I | awk '{print $1}')
PORT=${PORT:-8000}
HOST=${HOST:-0.0.0.0}

echo ""
echo "=========================================="
echo "  🚀 Запуск сервера..."
echo "=========================================="
echo ""
echo "  🌐 Локальный доступ: http://localhost:${PORT}"
echo "  🌐 Доступ из сети:   http://${LOCAL_IP}:${PORT}"
echo ""
echo "  📊 Endpoints мониторинга:"
echo "     - Health: http://localhost:${PORT}/health"
echo "     - Metrics: http://localhost:${PORT}/metrics"
echo "     - Stats: http://localhost:${PORT}/stats"
echo ""
echo "  📁 Директории данных:"
echo "     - Uploads: ${PROJECT_ROOT}/data/uploads"
echo "     - Reports: ${PROJECT_ROOT}/data/reports"
echo "     - Excel:   ${PROJECT_ROOT}/data/excel_files"
echo ""
echo "  ⚙️  Для остановки нажмите: Ctrl+C"
echo ""
echo "=========================================="
echo ""

# Запуск сервера с оптимизациями производительности
exec python3 -m uvicorn hr_app.backend.main:app \
    --host ${HOST} \
    --port ${PORT} \
    --workers 2 \
    --loop asyncio \
    --http h11
