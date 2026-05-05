# HR System v2.0 — Улучшенная версия

## 🚀 Что улучшено в версии 2.0

### Безопасность
- ✅ **CORS настроен** — теперь разрешены только localhost:8000, 127.0.0.1:8000
- ✅ **Валидация данных** — Pydantic модели для всех API endpoints
- ✅ **Логирование** — структурированные логи в `data/logs/hr_system.log`

### Тестирование
- ✅ **pytest тесты** — 13 тестов покрывают основные функции БД
- ✅ **Запуск тестов**: `pytest hr_app/tests/ -v`

### Интерфейс
- ✅ **Excel-подобные таблицы** — Handsontable для редактирования прямо в браузере
- ✅ **Улучшенный экспорт** — настоящий .xlsx через XlsxWriter

### Структура проекта
```
hr_app/
├── backend/
│   ├── main.py              # FastAPI приложение
│   ├── database.py          # SQLite слой
│   ├── routers/             # API endpoints с Pydantic
│   └── services/            # Бизнес-логика
├── frontend/
│   ├── index.html           # SPA интерфейс
│   └── static/
│       ├── css/style.css    # Стили
│       └── js/*.js          # Модули
├── tests/                   # pytest тесты
│   └── test_database.py
├── data/
│   ├── hr_system.db         # SQLite БД
│   └── logs/                # Логи
└── requirements.txt
```

## 📋 Запуск приложения

### Без Docker (рекомендуется)
```bash
# Установка зависимостей
pip install -r hr_app/requirements.txt xlsxwriter pytest

# Запуск сервера
cd /workspace
uvicorn hr_app.backend.main:app --host 0.0.0.0 --port 8000 --reload

# Открыть в браузере: http://localhost:8000
```

### Запуск тестов
```bash
cd /workspace/hr_app
python -m pytest tests/ -v
```

## 🔧 Конфигурация

### Переменные окружения (опционально)
Создайте файл `.env` в корне проекта:
```env
DATABASE_URL=sqlite:///hr_app/data/hr_system.db
LOG_LEVEL=INFO
HOST=0.0.0.0
PORT=8000
```

## 📊 Функционал

### Основные модули
- 👥 **Сотрудники** — учёт, фильтрация, поиск, Excel-таблица
- 📊 **Дашборд** — аналитика, графики, KPI
- 📈 **Отчёты** — численность, гражданство, динамика
- 📅 **Ежедневный учёт** — загрузка ЕЖУ файлов
- ✈️ **Билеты** — покупка и затраты
- 🛂 **OCR** — распознавание паспортов и документов
- ⚙️ **Утилиты** — дополнительные инструменты

### Excel-подобные таблицы
Теперь таблицы поддерживают:
- Редактирование ячеек как в Excel
- Копирование/вставка диапазонов
- Сортировка по колонкам
- Фильтрация данных
- Автосохранение изменений

## 🛠️ Разработка

### Добавление новых тестов
```python
# hr_app/tests/test_new_feature.py
def test_new_feature():
    assert True
```

### Добавление API endpoint
```python
# hr_app/backend/routers/new_module.py
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/new", tags=["new"])

class Item(BaseModel):
    name: str

@router.post("/create")
def create(item: Item):
    return {"status": "ok"}
```

## 📝 Changelog

### v2.0.0 (2026)
- ✅ CORS security fix
- ✅ Pydantic validation
- ✅ pytest tests (13 tests)
- ✅ Structured logging
- ✅ Excel-like tables (Handsontable)
- ✅ XlsxWriter export

### v1.0.0 (2025)
- Initial release

## 📄 Лицензия
Внутреннее корпоративное ПО
