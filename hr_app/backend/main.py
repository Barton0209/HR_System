"""
HR System Backend — FastAPI v2.0
Запуск: uvicorn hr_app.backend.main:app --host 0.0.0.0 --port 8000 --reload

Улучшения:
- Конфигурация через Pydantic Settings
- Единая система логирования (JSON)
- Rate limiting
- Хэширование паролей (bcrypt)
- Health checks и Prometheus метрики
- MRZ парсер
- Валидация загружаемых файлов
"""
import logging
import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from hr_app.backend.config import settings
from hr_app.backend.database import init_db
from hr_app.backend.middleware import RateLimitMiddleware, SecurityHeadersMiddleware
from hr_app.backend.routers import (
    dashboard, employees, reports, tickets, daily_tracking, ocr, settings as settings_router,
    utilities, carnet, auth, monitoring
)

# ==========================================================================
# НАСТРОЙКА ЛОГИРОВАНИЯ (Structured JSON Logging)
# ==========================================================================

def setup_logging():
    """Настройка структурированного JSON логирования."""
    log_folder = settings.log_folder
    log_folder.mkdir(parents=True, exist_ok=True)
    
    # Настройка structlog для JSON логов
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer() if settings.log_format == "json" 
            else structlog.dev.ConsoleRenderer()
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Стандартный logging для библиотек
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper()),
    )
    
    # Файловый обработчик
    file_handler = logging.FileHandler(
        log_folder / "hr_system.log", 
        encoding="utf-8"
    )
    file_handler.setLevel(getattr(logging, settings.log_level.upper()))
    logging.getLogger().addHandler(file_handler)
    
    return structlog.get_logger()

logger = setup_logging()


# ==========================================================================
# LIFESPAN EVENTS
# ==========================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """События запуска и остановки приложения."""
    # Startup
    logger.info("HR System starting up")
    
    # Валидация путей
    settings.validate_paths()
    
    # Инициализация БД
    init_db()
    
    logger.info("Database initialized")
    logger.info(f"Upload folder: {settings.upload_folder}")
    logger.info(f"Reports folder: {settings.reports_folder}")
    
    yield
    
    # Shutdown
    logger.info("HR System shutting down")


# ==========================================================================
# ПРИЛОЖЕНИЕ FASTAPI
# ==========================================================================

app = FastAPI(
    title="HR System API",
    description="Система управления персоналом с OCR и MRZ",
    version="2.0.0",
    lifespan=lifespan
)

# ==========================================================================
# MIDDLEWARE
# ==========================================================================

# CORS - разрешаем доступ из локальной сети
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# Rate limiting
app.add_middleware(
    RateLimitMiddleware,
    requests_per_minute=settings.rate_limit_per_minute
)

# Заголовки безопасности
app.add_middleware(SecurityHeadersMiddleware)

# ==========================================================================
# ROUTERS
# ==========================================================================

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(employees.router, prefix="/api/employees", tags=["employees"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])
app.include_router(tickets.router, prefix="/api/tickets", tags=["tickets"])
app.include_router(daily_tracking.router, prefix="/api/daily-tracking", tags=["daily-tracking"])
app.include_router(ocr.router, prefix="/api/ocr", tags=["ocr"])
app.include_router(settings_router.router, prefix="/api/settings", tags=["settings"])
app.include_router(utilities.router, prefix="/api/utilities", tags=["utilities"])
app.include_router(carnet.router, prefix="/api/carnet", tags=["carnet"])
app.include_router(monitoring.router)  # Health checks и метрики без префикса

# ==========================================================================
# STATIC FILES
# ==========================================================================

STATIC_DIR = Path(__file__).parent.parent / "frontend" / "static"
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
def serve_index():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.get("/{path:path}", include_in_schema=False)
def serve_spa(path: str):
    fp = FRONTEND_DIR / path
    if fp.exists() and fp.is_file():
        return FileResponse(str(fp))
    return FileResponse(str(FRONTEND_DIR / "index.html"))


# ==========================================================================
# GLOBAL EXCEPTION HANDLER
# ==========================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Глобальный обработчик исключений."""
    logger.error(
        "Unhandled exception",
        path=str(request.url.path),
        method=request.method,
        error=str(exc),
        exc_info=True
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Внутренняя ошибка сервера", "error_type": type(exc).__name__}
    )
