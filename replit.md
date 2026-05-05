# HR Management System

## Overview
Modern web-based HR management system built with FastAPI (Python) + Vanilla JS frontend. Designed for internal LAN network access. Integrates with local Ollama AI models for OCR processing.

## Architecture
- **Backend**: FastAPI + SQLite (sqlite3 direct) — no ORM
- **Frontend**: Vanilla JS SPA, Chart.js (CDN), dark theme
- **AI**: Ollama integration (glm-ocr:latest, qwen2.5vl:latest, qwen2.5-coder:1.5b)
- **Port**: 5000 (Replit), 8000 (local Windows LAN via run_hr_system.bat)

## Project Structure
```
hr_app/
├── backend/
│   ├── main.py              # FastAPI entry point
│   ├── database.py          # SQLite DB: all tables + queries
│   ├── services/
│   │   ├── excel_service.py # БАЗА.xlsx loading (43-col mapping)
│   │   ├── ollama_service.py# Ollama AI integration
│   │   └── pdf_service.py   # PDF processing
│   └── routers/
│       ├── dashboard.py     # Dashboard + KPIs + filters
│       ├── employees.py     # Employee CRUD
│       ├── reports.py       # 50+ report types
│       ├── tickets.py       # Ticket purchase + costs
│       ├── daily_tracking.py# Daily tracking (Ежедневный учёт)
│       ├── ocr.py           # OCR passport + docs via Ollama
│       ├── settings.py      # Settings + БАЗА.xlsx upload
│       └── utilities.py     # Transliteration, ticket parser, stazh
├── frontend/
│   ├── index.html           # SPA with 13 nav tabs
│   └── static/
│       ├── css/style.css    # Dark theme CSS
│       └── js/
│           ├── app.js       # Core navigation, API helpers, Charts
│           ├── dashboard.js # Dashboard logic + charts
│           ├── employees.js # Employee table
│           ├── reports.js   # Reports module
│           ├── tickets.js   # Tickets module
│           ├── daily_tracking.js
│           ├── ocr.js       # OCR interface
│           ├── settings.js  # Settings + file upload
│           └── utilities.js # Full utilities: translit/tickets/rename/stazh
├── data/                    # SQLite DB + logs + uploads
└── requirements.txt
run_hr_system.bat            # Windows LAN launcher
```

## Key Features
1. **Dashboard** — 3 mode filters (ALL/ACTIVE/FINISHED), KPIs, charts
2. **Employees** — 43-column БАЗА.xlsx import, CRUD, search/filter
3. **Reports** — 50+ report types, Excel export
4. **Daily Tracking** — Ежедневный учёт
5. **Tickets** — Purchase tracking + cost analysis
6. **Evaluations** — РОП/ИТР evaluation forms
7. **OCR** — Passport/document OCR via Ollama (glm-ocr, qwen2.5vl)
8. **Utilities**:
   - Transliterator: 23 countries, country-specific maps (CIS/Belarus/Serbia/Croatia/Azerbaijan/Ukraine/Macedonia)
   - PDF Ticket Parser: extracts passenger, flight, route, price from PDF tickets
   - File Renamer: prefix/suffix/pattern/replace/case modes with live preview
   - Employee Stazh (tenure) calculator: filterable, Excel export

## Running Locally (Windows)
```
run_hr_system.bat
```
Access: http://localhost:8000 or http://{COMPUTERNAME}:8000

## Data Source
- Main DB: `БАЗА.xlsx` (43 columns, A=unique1 through AQ=doc_type)
- Upload via Settings tab → База сотрудников
- Ollama URL: http://localhost:11434 (configurable in Settings)

## Dependencies
```
fastapi, uvicorn[standard], python-multipart, httpx
pandas, openpyxl, pdfplumber, PyPDF2, aiofiles
```
