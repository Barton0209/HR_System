@echo off
chcp 65001 >nul
title HR System - Запуск
echo =============================================
echo   HR MANAGEMENT SYSTEM — Запуск
echo =============================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] Python не найден. Установите Python 3.10+
    pause
    exit /b 1
)

:: Go to script directory
cd /d "%~dp0"

:: Install dependencies if needed
echo [1/3] Проверка зависимостей...
pip install -q -r hr_app/requirements.txt

:: Create data directories
echo [2/3] Создание рабочих папок...
if not exist "data" mkdir data
if not exist "data\uploads" mkdir data\uploads
if not exist "data\EJU\Download" mkdir data\EJU\Download

:: Start server
echo [3/3] Запуск сервера...
echo.
echo  Адрес: http://localhost:8000
echo  LAN:   http://%COMPUTERNAME%:8000
echo.
echo  Для остановки нажмите Ctrl+C
echo =============================================
echo.

:: Try uvicorn directly first, then as module
where uvicorn >nul 2>&1
if not errorlevel 1 (
    uvicorn hr_app.backend.main:app --host 0.0.0.0 --port 8000 --reload
) else (
    python -m uvicorn hr_app.backend.main:app --host 0.0.0.0 --port 8000 --reload
)

:: Note: Replit preview uses port 5000. Local Windows LAN uses port 8000.

pause
