@echo off
chcp 65001 > nul
echo ============================================
echo   Система заявок на билеты v2.0
echo ============================================

:: Проверяем Python
python --version > nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] Python не найден! Установите Python 3.11+
    pause
    exit /b 1
)

:: Переходим в папку проекта
cd /d "%~dp0"

:: Устанавливаем зависимости если нужно
if not exist "venv\" (
    echo Создание виртуального окружения...
    python -m venv venv
    call venv\Scripts\activate.bat
    echo Установка зависимостей...
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate.bat
)

:: Копируем .env если не существует
if not exist ".env" (
    echo Создание .env из шаблона...
    copy .env.example .env
    echo [ВНИМАНИЕ] Отредактируйте .env файл перед запуском!
    notepad .env
)

:: Запускаем приложение
echo Запуск приложения...
cd ticket_app
python main.py

pause
