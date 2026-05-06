# HR System v2.0 - Changelog

## Версия 2.0.0 (Текущая)

### 🔒 Безопасность
- ✅ Хэширование паролей через bcrypt вместо SHA-256
- ✅ Rate limiting middleware (60 запросов/минуту на IP)
- ✅ Заголовки безопасности (X-Content-Type-Options, X-Frame-Options, XSS-Protection)
- ✅ Валидация загружаемых файлов (санитизация имён, проверка расширений)
- ✅ Ограничение размера загружаемых файлов (100MB)

### ⚙️ Конфигурация
- ✅ Pydantic Settings для управления конфигурацией
- ✅ Поддержка .env файла
- ✅ Централизованные настройки через `backend/config.py`

### 📊 Мониторинг
- ✅ Health check endpoints (`/health`, `/health/live`, `/health/ready`)
- ✅ Prometheus метрики (`/metrics`)
- ✅ Statistics endpoint (`/stats`)
- ✅ Structured JSON логирование через structlog

### 🔧 Архитектура
- ✅ Модульная структура зависимостей в requirements.txt
- ✅ Единая система логирования
- ✅ Lifespan events для startup/shutdown
- ✅ Global exception handler

### 🆕 Новые функции
- ✅ MRZ парсер для российских паспортов (TD3)
- ✅ Кэширование результатов OCR (готово к реализации)
- ✅ Интеграция справочников из Excel:
  - ПАРОЛЬ_ДОСТУП.xlsx
  - Подразделение_Отдел_Участок.xlsx
  - Терр_ПЛОЩ_ПОДР_СтатусОП_Регион.xlsx
  - Должность, Классификация.xlsx
- ✅ Генерация отчетов:
  - ОБЩИЙ_СТАЖ.xlsx
  - Реестр_по_затратам_на_билеты.xlsx

### 🛠️ Исправления
- ✅ Удалено дублирование зависимостей в requirements.txt
- ✅ Создан .env файл для локальной разработки
- ✅ Создан .gitignore с правильными исключениями
- ✅ Убраны хардкод Windows-путей из документации

### 📁 Файловая структура
```
hr_app/
├── .env                    # Локальные настройки
├── .env.example            # Шаблон настроек
├── .gitignore              # Игнорируемые файлы
├── requirements.txt        # Зависимости Python
├── start_server.sh         # Скрипт запуска
├── backend/
│   ├── config.py           # Pydantic Settings
│   ├── main.py             # Точка входа FastAPI
│   ├── middleware.py       # Rate limiting, Security headers
│   ├── database.py         # Работа с SQLite
│   ├── routers/
│   │   ├── auth.py         # Аутентификация (bcrypt)
│   │   ├── settings.py     # Настройки и загрузка Excel
│   │   ├── monitoring.py   # Health checks, Prometheus
│   │   └── ...
│   └── services/
│       ├── excel_service.py    # Обработка Excel
│       ├── mrz_parser.py       # MRZ парсер
│       └── ...
├── frontend/
│   ├── index.html
│   └── static/
└── data/
    ├── uploads/            # Загруженные файлы
    ├── reports/            # Сгенерированные отчеты
    ├── logs/               # Логи приложения
    ├── mrz_cache/          # Кэш MRZ
    └── ocr_cache/          # Кэш OCR
```

### 🚀 Запуск

```bash
cd hr_app
./start_server.sh
```

**Адреса доступа:**
- Локально: http://localhost:8000
- Из сети: http://<ВАШ_IP>:8000

**Endpoints мониторинга:**
- Health: http://localhost:8000/health
- Metrics: http://localhost:8000/metrics
- Stats: http://localhost:8000/stats

---

## Версия 1.0.0 (Предыдущая)

- Базовая функциональность HR системы
- CRUD операции с сотрудниками
- Загрузка основной базы из Excel
- Простая аутентификация
- Отчёты по сотрудникам
