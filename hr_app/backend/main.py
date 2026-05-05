"""
HR System Backend — FastAPI
Запуск: uvicorn hr_app.backend.main:app --host 0.0.0.0 --port 8000 --reload
"""
import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from hr_app.backend.database import init_db
from hr_app.backend.routers import (
    dashboard, employees, reports, tickets, daily_tracking, ocr, settings, utilities
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("data/hr_system.log", encoding="utf-8"),
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="HR System API",
    description="Система управления персоналом",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(dashboard.router)
app.include_router(employees.router)
app.include_router(reports.router)
app.include_router(tickets.router)
app.include_router(daily_tracking.router)
app.include_router(ocr.router)
app.include_router(settings.router)
app.include_router(utilities.router)

# Static files
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


@app.on_event("startup")
def on_startup():
    Path("data").mkdir(exist_ok=True)
    Path("data/uploads").mkdir(exist_ok=True)
    Path("data/EJU/Download").mkdir(parents=True, exist_ok=True)
    init_db()
    logger.info("HR System started")
