# IDPS v2.0 + Ticket Processing System

Интегрированная система обработки документов с модулем заявок на билеты.

## Компоненты

### 1. IDPS Core (Intelligent Document Processing System)
- **OCR Engine** - Адаптивное распознавание текста (Tesseract, PaddleOCR, TrOCR)
- **NLP Layer** - Извлечение сущностей и классификация (ruBERT, DeepPavlov)
- **PostgreSQL** - База данных с полнотекстовым поиском
- **FastAPI Gateway** - REST API для загрузки и обработки

### 2. Ticket Application (Заявки на билеты)
- Обработка PDF-заявок на авиабилеты
- База сотрудников (Excel → PostgreSQL)
- Автозаполнение из базы
- Экспорт в Excel

## Быстрый старт

### Локальная разработка
```bash
# 1. Установка зависимостей
pip install -r requirements.txt

# 2. Настройка переменных окружения
cp .env.example .env
# Отредактируйте .env

# 3. Запуск через Docker Compose
docker-compose up -d

# 4. Инициализация БД
make db-init

# 5. Запуск Ticket App (GUI)
python ticket_app/main.py
```

### Production (Kubernetes + Helm)
```bash
# 1. Установка Helm Chart
helm install idps charts/idps -f charts/idps/values.yaml

# 2. Проверка статуса
kubectl get pods -n idps

# 3. Доступ к UI
kubectl port-forward svc/idps-ingestor 8000:8000
```

## Архитектура

```
┌─────────────────────────────────────────────────────────┐
│                    IDPS v2.0 Stack                      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────┐    ┌──────────────┐                 │
│  │ Ticket App   │───▶│  Ingestor    │                 │
│  │  (tkinter)   │    │  (FastAPI)   │                 │
│  └──────────────┘    └───────┬──────┘                 │
│                              │                          │
│         ┌────────────────────┼────────────────┐        │
│         ▼                    ▼                 ▼        │
│  ┌──────────┐        ┌──────────┐      ┌──────────┐   │
│  │ OCR Core │        │   NLP    │      │PostgreSQL│   │
│  │(Adaptive)│        │  Layer   │      │  + Redis │   │
│  └──────────┘        └──────────┘      └──────────┘   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## Структура проекта

```
idps/
├── config/                    # Конфигурация
│   ├── ocr_selector.yaml     # Правила выбора OCR-модели
│   └── app_config.yaml       # Настройки приложения
├── infrastructure/
│   └── postgresql/
│       ├── schema.sql        # Схема БД
│       └── seed.sql          # Начальные данные
├── ocr_core/                 # OCR-движок
│   ├── ocr_selector.py       # Эвристика выбора модели
│   ├── main.py               # FastAPI сервис
│   └── requirements.txt
├── nlp_layer/                # NLP-обработка
│   ├── main.py
│   └── requirements.txt
├── ingestor/                 # API Gateway
│   ├── main.py
│   └── requirements.txt
├── ticket_app/               # GUI приложение заявок
│   ├── main.py               # Главное окно
│   ├── auth.py               # Авторизация
│   ├── database.py           # Работа с БД
│   ├── pdf_processor.py      # Обработка PDF
│   ├── excel_handler.py      # Экспорт в Excel
│   ├── dialogs/              # Диалоговые окна
│   │   ├── catalog.py
│   │   ├── wizard.py
│   │   └── pdf_viewer.py
│   └── requirements.txt
├── charts/                   # Helm Charts
│   └── idps/
│       ├── Chart.yaml
│       ├── values.yaml
│       └── templates/
├── docker-compose.yml        # Локальная разработка
├── Makefile                  # Команды сборки
└── README.md
```

## Функционал Ticket App

### Обработка заявок
1. **Загрузка PDF** - Автоматическое извлечение ФИО, маршрутов, дат
2. **Поиск в базе** - Автоматический поиск сотрудника по ФИО
3. **Ручная корректировка** - Визард с просмотром PDF
4. **Экспорт** - Формирование Excel-файла заявки

### База сотрудников
- Загрузка из Excel (любая структура)
- Автоматическое сопоставление колонок
- Поиск по ФИО, табельному номеру, паспорту
- Каталог с фильтрацией

### Безопасность
- Хэширование паролей (SHA-256)
- Хранение учётных данных в `.env`
- Разделение прав (Admin / ОП)

## API Endpoints

### IDPS Core
- `POST /documents/upload` - Загрузка документа
- `GET /documents/{id}/status` - Статус обработки
- `GET /documents/{id}/result` - Результат OCR+NLP

### Ticket App Integration
- `POST /api/tickets/process` - Обработка PDF-заявки
- `GET /api/employees/search` - Поиск сотрудника
- `POST /api/tickets/export` - Экспорт в Excel

## Конфигурация

### .env файл
```env
# PostgreSQL
DATABASE_URL=postgresql://idps:idps@localhost:5432/idps

# Tesseract
TESSERACT_PATH=C:\Program Files\Tesseract-OCR\tesseract.exe

# Пароли (хэшируются автоматически)
ADMIN_PASSWORD=your_secure_password
OP_KINGISEPP=password123

# OCR
OCR_DEFAULT_MODEL=PaddleOCR-VL-0.9B
OCR_GPU_ENABLED=false
```

## Разработка

### Добавление нового ОП
1. Добавьте в `.env`:
   ```env
   OP_NEW_BRANCH=password456
   ```
2. Обновите `config.py`:
   ```python
   _OP_ENV_MAP = {
       "ОП Новое подразделение": "OP_NEW_BRANCH",
   }
   ```

### Тестирование OCR
```bash
# Тест на одном файле
python -m ocr_core.ocr_selector test.pdf --lang ru

# Бенчмарк моделей
python -m ocr_core.benchmark --dataset data/test/
```

## Мониторинг

### Grafana Dashboard
- OCR Accuracy (последние 24ч)
- Количество обработанных документов
- Средняя уверенность распознавания

### Логи
```bash
# Просмотр логов OCR
docker-compose logs -f ocr-core

# Логи Ticket App
tail -f logs/ticket_app.log
```

## Лицензия

MIT License - свободное использование для коммерческих и некоммерческих целей.

## Поддержка

- Документация: [docs/](docs/)
- Issues: GitHub Issues
- Email: support@example.com
