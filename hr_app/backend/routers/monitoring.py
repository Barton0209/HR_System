"""
Health Checks и Prometheus метрики для мониторинга
"""
import os
import time
import logging
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, Response
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

logger = logging.getLogger(__name__)

router = APIRouter(tags=["monitoring"])

# ==========================================================================
# PROMETHEUS МЕТРИКИ
# ==========================================================================

# Счётчики
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint'],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
)

# Гauges
active_connections = Gauge(
    'active_connections',
    'Number of active connections'
)

database_size_bytes = Gauge(
    'database_size_bytes',
    'Database file size in bytes'
)

uptime_seconds = Gauge(
    'uptime_seconds',
    'Application uptime in seconds'
)

# Время старта приложения
START_TIME = time.time()
uptime_seconds.set(0)


def update_uptime():
    """Обновление метрики uptime."""
    uptime_seconds.set(time.time() - START_TIME)


def update_database_metrics(db_path: str):
    """Обновление метрик базы данных."""
    try:
        path = Path(db_path)
        if path.exists():
            database_size_bytes.set(path.stat().st_size)
    except Exception as e:
        logger.error(f"Ошибка обновления метрик БД: {e}")


# ==========================================================================
# HEALTH CHECKS
# ==========================================================================

@router.get("/health")
async def health_check():
    """
    Полный health check приложения.
    Проверяет все критические компоненты.
    """
    update_uptime()
    
    checks = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {}
    }
    
    # Проверка базы данных
    try:
        from hr_app.backend.database import get_conn
        conn = get_conn()
        conn.execute("SELECT 1")
        checks["checks"]["database"] = {"status": "healthy"}
    except Exception as e:
        checks["checks"]["database"] = {"status": "unhealthy", "error": str(e)}
        checks["status"] = "unhealthy"
    
    # Проверка директорий
    required_dirs = ["data/uploads", "data/reports", "data/logs"]
    for dir_path in required_dirs:
        try:
            path = Path(dir_path)
            if not path.exists():
                path.mkdir(parents=True, exist_ok=True)
            if not os.access(str(path), os.W_OK):
                raise PermissionError(f"No write access to {dir_path}")
            checks["checks"][f"dir_{dir_path.replace('/', '_')}"] = {"status": "healthy"}
        except Exception as e:
            checks["checks"][f"dir_{dir_path.replace('/', '_')}"] = {
                "status": "unhealthy", 
                "error": str(e)
            }
            checks["status"] = "degraded"
    
    # Проверка файла с паролями (опционально)
    passwords_file = Path(os.getenv("PASSWORDS_FILE", "Excel_files/ПАРОЛЬ_ДОСТУП.xlsx"))
    if passwords_file.exists():
        checks["checks"]["passwords_file"] = {"status": "healthy"}
    else:
        checks["checks"]["passwords_file"] = {
            "status": "warning", 
            "message": "Файл паролей не найден"
        }
    
    status_code = 200 if checks["status"] == "healthy" else 503
    return Response(
        content=str(checks).replace("'", '"'),
        media_type="application/json",
        status_code=status_code
    )


@router.get("/health/live")
async def liveness_probe():
    """
    Liveness probe для Kubernetes/Docker.
    Просто проверяет, что приложение запущено.
    """
    return {"status": "alive", "timestamp": datetime.utcnow().isoformat()}


@router.get("/health/ready")
async def readiness_probe():
    """
    Readiness probe для Kubernetes/Docker.
    Проверяет готовность обрабатывать запросы.
    """
    try:
        # Быстрая проверка БД
        from hr_app.backend.database import get_conn
        conn = get_conn()
        conn.execute("SELECT 1")
        return {"status": "ready", "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        return Response(
            content='{"status": "not_ready", "error": "' + str(e) + '"}',
            media_type="application/json",
            status_code=503
        )


@router.get("/metrics")
async def metrics():
    """
    Endpoint для Prometheus метрик.
    Возвращает метрики в формате Prometheus.
    """
    update_uptime()
    
    # Обновляем метрики БД
    try:
        from hr_app.backend.config import settings
        update_database_metrics(str(settings.database_path))
    except Exception:
        pass
    
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


@router.get("/stats")
async def statistics():
    """
    Статистика приложения в удобном формате.
    """
    update_uptime()
    
    uptime = time.time() - START_TIME
    days = int(uptime // 86400)
    hours = int((uptime % 86400) // 3600)
    minutes = int((uptime % 3600) // 60)
    
    stats = {
        "uptime": f"{days}d {hours}h {minutes}m",
        "uptime_seconds": round(uptime, 2),
        "start_time": datetime.fromtimestamp(START_TIME).isoformat(),
        "current_time": datetime.utcnow().isoformat(),
        "version": "2.0.0"
    }
    
    # Добавляем информацию о БД
    try:
        from hr_app.backend.database import get_conn, DB_PATH
        conn = get_conn()
        
        # Количество сотрудников
        emp_count = conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0]
        stats["employees_count"] = emp_count
        
        # Размер БД
        if DB_PATH.exists():
            db_size_mb = round(DB_PATH.stat().st_size / 1024 / 1024, 2)
            stats["database_size_mb"] = db_size_mb
    except Exception as e:
        stats["database_error"] = str(e)
    
    return stats
