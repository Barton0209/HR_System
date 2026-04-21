# ingestor/main.py
"""
Ingestor API Gateway — принимает документы, оркестрирует OCR + NLP.
"""

import os
import uuid
import logging
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="IDPS Ingestor", version="2.0.0")

OCR_URL = os.getenv("OCR_URL", "http://localhost:8001")
NLP_URL = os.getenv("NLP_URL", "http://localhost:8002")
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "/tmp/idps_ingestor"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# In-memory хранилище статусов (в prod — Redis/PostgreSQL)
_jobs: dict[str, dict] = {}


async def _process_pipeline(job_id: str, file_path: Path, filename: str, lang: str, doc_type: str):
    """Фоновая задача: OCR → NLP → сохранение результата."""
    _jobs[job_id]["status"] = "preprocessed"
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            # 1. OCR
            with open(file_path, "rb") as f:
                ocr_resp = await client.post(
                    f"{OCR_URL}/ocr/process",
                    files={"file": (filename, f, "application/pdf")},
                    params={"lang": lang, "doc_type": doc_type},
                )
            ocr_data = ocr_resp.json()
            _jobs[job_id]["status"] = "ocr_completed"
            _jobs[job_id]["ocr"] = ocr_data

            # 2. NLP на каждой странице
            nlp_results = []
            for page in ocr_data.get("pages", []):
                nlp_resp = await client.post(
                    f"{NLP_URL}/nlp/process",
                    json={"text": page.get("text", ""), "doc_type": doc_type},
                )
                nlp_results.append(nlp_resp.json())

            _jobs[job_id]["status"] = "nlp_completed"
            _jobs[job_id]["nlp"] = nlp_results
            _jobs[job_id]["status"] = "finished"

    except Exception as e:
        logger.error("Pipeline error for job %s: %s", job_id, e)
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["error"] = str(e)
    finally:
        file_path.unlink(missing_ok=True)


@app.get("/health")
def health():
    return {"status": "ok", "service": "ingestor"}


@app.post("/documents/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    lang: str = "rus+eng",
    doc_type: Optional[str] = None,
):
    """Загружает документ и запускает обработку в фоне."""
    job_id = str(uuid.uuid4())
    suffix = Path(file.filename).suffix.lower()

    if suffix not in (".pdf", ".png", ".jpg", ".jpeg", ".tiff"):
        raise HTTPException(400, "Неподдерживаемый формат файла")

    save_path = UPLOAD_DIR / f"{job_id}{suffix}"
    content = await file.read()
    save_path.write_bytes(content)

    _jobs[job_id] = {
        "status": "uploaded",
        "filename": file.filename,
        "job_id": job_id,
    }

    background_tasks.add_task(
        _process_pipeline, job_id, save_path, file.filename, lang, doc_type or "заявка"
    )

    return JSONResponse({
        "id": job_id,
        "status": "uploaded",
        "status_url": f"/documents/{job_id}/status",
        "result_url": f"/documents/{job_id}/result",
    }, status_code=202)


@app.get("/documents/{job_id}/status")
def get_status(job_id: str):
    if job_id not in _jobs:
        raise HTTPException(404, "Задача не найдена")
    return {"job_id": job_id, "status": _jobs[job_id]["status"]}


@app.get("/documents/{job_id}/result")
def get_result(job_id: str):
    if job_id not in _jobs:
        raise HTTPException(404, "Задача не найдена")
    job = _jobs[job_id]
    if job["status"] not in ("finished", "failed"):
        raise HTTPException(202, f"Обработка: {job['status']}")
    return job


@app.get("/documents")
def list_documents():
    return [
        {"job_id": jid, "filename": j["filename"], "status": j["status"]}
        for jid, j in _jobs.items()
    ]


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
