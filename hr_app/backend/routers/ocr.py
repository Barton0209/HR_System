import os
import tempfile
from fastapi import APIRouter, UploadFile, File, Form, Query
from hr_app.backend.services.ollama_service import (
    check_ollama, ocr_image_with_ollama, analyze_document
)

router = APIRouter(prefix="/api/ocr", tags=["ocr"])


@router.get("/status")
async def ollama_status():
    return await check_ollama()


@router.post("/passport")
async def ocr_passport(
    file: UploadFile = File(...),
    model: str = Form("glm-ocr:latest"),
):
    content = await file.read()
    suffix = os.path.splitext(file.filename)[1] or ".jpg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(content)
        tmp_path = f.name

    try:
        result = await analyze_document(tmp_path, doc_type="passport_ru")
        return {"ok": True, "result": result, "filename": file.filename}
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


@router.post("/document")
async def ocr_document(
    file: UploadFile = File(...),
    doc_type: str = Form("auto"),
    model: str = Form("glm-ocr:latest"),
):
    content = await file.read()
    suffix = os.path.splitext(file.filename)[1] or ".jpg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(content)
        tmp_path = f.name

    try:
        result = await analyze_document(tmp_path, doc_type=doc_type)
        return {"ok": True, "result": result, "filename": file.filename}
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


@router.post("/batch")
async def ocr_batch(
    files: list[UploadFile] = File(...),
    doc_type: str = Form("auto"),
    model: str = Form("glm-ocr:latest"),
):
    results = []
    for file in files:
        content = await file.read()
        suffix = os.path.splitext(file.filename)[1] or ".jpg"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(content)
            tmp_path = f.name
        try:
            result = await analyze_document(tmp_path, doc_type=doc_type)
            results.append({"filename": file.filename, "result": result})
        except Exception as e:
            results.append({"filename": file.filename, "error": str(e)})
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
    return {"results": results}
