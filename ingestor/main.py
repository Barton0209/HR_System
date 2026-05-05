# ingestor/main.py
"""
Ingestor API Gateway — принимает документы, оркестрирует OCR + NLP, сохраняет в БД.
Порт: 8000
"""
import os
import uuid
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

import httpx
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="IDPS Ingestor", version="2.0.0", docs_url="/api/docs")

OCR_URL = os.getenv("OCR_URL", "http://localhost:8001")
NLP_URL = os.getenv("NLP_URL", "http://localhost:8002")
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "/tmp/idps_ingestor"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Веб-интерфейс
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "web_ui" / "templates"))
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent.parent / "web_ui" / "static")), name="static")

# In-memory хранилище (в prod — PostgreSQL)
_jobs: dict[str, dict] = {}


# ── Фоновая обработка ─────────────────────────────────────────────────────────

async def _pipeline(job_id: str, file_path: Path, filename: str, lang: str, doc_type: str):
    _jobs[job_id]["status"] = "preprocessed"
    try:
        async with httpx.AsyncClient(timeout=180) as client:
            # 1. OCR
            with open(file_path, "rb") as f:
                ocr_resp = await client.post(
                    f"{OCR_URL}/ocr/process",
                    files={"file": (filename, f, "application/octet-stream")},
                    params={"lang": lang},
                )
            ocr_data = ocr_resp.json()
            _jobs[job_id]["status"] = "ocr_completed"
            _jobs[job_id]["ocr"] = ocr_data

            # 2. NLP — определяем тип документа и извлекаем сущности
            full_text = "\n".join(p.get("text", "") for p in ocr_data.get("pages", []))
            
            # Классификация
            classify_resp = await client.post(
                f"{NLP_URL}/nlp/classify",
                json={"text": full_text, "doc_type": doc_type}
            )
            classification = classify_resp.json()
            detected_type = classification.get("doc_class", "unknown")

            # Специализированное извлечение
            if detected_type in ("passport_ru", "passport_foreign"):
                nlp_resp = await client.post(
                    f"{NLP_URL}/nlp/passport",
                    json={"text": full_text}
                )
            elif detected_type == "ticket_request":
                nlp_resp = await client.post(
                    f"{NLP_URL}/nlp/ticket",
                    json={"text": full_text}
                )
            else:
                nlp_resp = await client.post(
                    f"{NLP_URL}/nlp/process",
                    json={"text": full_text, "doc_type": doc_type}
                )

            nlp_data = nlp_resp.json()
            _jobs[job_id]["status"] = "nlp_completed"
            _jobs[job_id]["nlp"] = nlp_data
            _jobs[job_id]["doc_class"] = detected_type
            _jobs[job_id]["status"] = "finished"
            _jobs[job_id]["finished_at"] = datetime.now().isoformat()

    except Exception as e:
        logger.exception("Pipeline error for job %s", job_id)
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["error"] = str(e)
    finally:
        file_path.unlink(missing_ok=True)


# ── API Endpoints ─────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Главная страница — веб-интерфейс загрузки документов."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
def health():
    return {"status": "ok", "service": "ingestor", "ocr_url": OCR_URL, "nlp_url": NLP_URL}


@app.post("/api/documents/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    lang: str = "rus+eng",
    doc_type: Optional[str] = None,
):
    """
    Загружает документ и запускает обработку в фоне.
    
    Параметры:
    - file: PDF, PNG, JPG, TIFF
    - lang: язык OCR (rus+eng, eng, rus)
    - doc_type: подсказка типа (passport, ticket_request, invoice, contract)
    """
    job_id = str(uuid.uuid4())
    suffix = Path(file.filename or "file.pdf").suffix.lower()

    if suffix not in (".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp"):
        raise HTTPException(400, f"Неподдерживаемый формат: {suffix}")

    save_path = UPLOAD_DIR / f"{job_id}{suffix}"
    save_path.write_bytes(await file.read())

    _jobs[job_id] = {
        "job_id": job_id,
        "filename": file.filename,
        "status": "uploaded",
        "uploaded_at": datetime.now().isoformat(),
    }

    background_tasks.add_task(_pipeline, job_id, save_path, file.filename, lang, doc_type or "")

    return JSONResponse({
        "id": job_id,
        "status": "uploaded",
        "status_url": f"/api/documents/{job_id}/status",
        "result_url": f"/api/documents/{job_id}/result",
    }, status_code=202)


@app.get("/api/documents/{job_id}/status")
def get_status(job_id: str):
    if job_id not in _jobs:
        raise HTTPException(404, "Задача не найдена")
    return {"job_id": job_id, "status": _jobs[job_id]["status"]}


@app.get("/api/documents/{job_id}/result")
def get_result(job_id: str):
    if job_id not in _jobs:
        raise HTTPException(404, "Задача не найдена")
    job = _jobs[job_id]
    if job["status"] not in ("finished", "failed"):
        return JSONResponse(
            {"job_id": job_id, "status": job["status"], "message": "Обработка..."},
            status_code=202
        )
    return job


@app.get("/api/documents")
def list_documents(limit: int = 50):
    """Список всех обработанных документов."""
    items = sorted(_jobs.values(), key=lambda x: x.get("uploaded_at", ""), reverse=True)
    return {"total": len(items), "items": items[:limit]}


@app.delete("/api/documents/{job_id}")
def delete_document(job_id: str):
    if job_id not in _jobs:
        raise HTTPException(404, "Задача не найдена")
    del _jobs[job_id]
    return {"message": "Удалено"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
