# ocr_core/main.py
"""
OCR Core Service — FastAPI микросервис для распознавания текста.
"""

import os
import uuid
import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

from ocr_selector import select_ocr_model

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="IDPS OCR Core", version="2.0.0")

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "/tmp/idps_uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

TESSERACT_PATH = os.getenv(
    "TESSERACT_PATH",
    r"C:\Users\DerevyankoGA\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
)


def _run_tesseract_ocr(image_path: Path, lang: str = "rus+eng") -> tuple[str, float]:
    """Запускает Tesseract OCR и возвращает (текст, уверенность)."""
    try:
        import pytesseract
        import cv2
        import numpy as np
        from PIL import Image as PILImage

        pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

        img = cv2.imread(str(image_path))
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)
        gray = cv2.medianBlur(gray, 3)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        pil_img = PILImage.fromarray(binary)
        data = pytesseract.image_to_data(
            pil_img, lang=lang, config="--psm 6 --oem 3",
            output_type=pytesseract.Output.DICT
        )
        text = pytesseract.image_to_string(pil_img, lang=lang, config="--psm 6 --oem 3")

        confs = [int(c) for c in data["conf"] if str(c).isdigit() and int(c) >= 0]
        confidence = sum(confs) / len(confs) / 100 if confs else 0.0

        return text, confidence
    except Exception as e:
        logger.error("Tesseract error: %s", e)
        return "", 0.0


def _process_pdf(pdf_path: Path, lang: str = "rus+eng") -> list[dict]:
    """Обрабатывает PDF постранично."""
    try:
        import fitz
        doc = fitz.open(str(pdf_path))
        results = []
        for i, page in enumerate(doc):
            native_text = page.get_text().strip()
            if len(native_text) > 50:
                results.append({
                    "page": i + 1,
                    "text": native_text,
                    "confidence": 1.0,
                    "engine": "native"
                })
            else:
                pix = page.get_pixmap(matrix=fitz.Matrix(3, 3), alpha=False)
                tmp_img = UPLOAD_DIR / f"page_{i}.png"
                pix.save(str(tmp_img))
                text, conf = _run_tesseract_ocr(tmp_img, lang)
                tmp_img.unlink(missing_ok=True)
                results.append({
                    "page": i + 1,
                    "text": text,
                    "confidence": conf,
                    "engine": "tesseract"
                })
        doc.close()
        return results
    except Exception as e:
        logger.error("PDF processing error: %s", e)
        return []


@app.get("/health")
def health():
    return {"status": "ok", "service": "ocr-core"}


@app.post("/ocr/process")
async def process_document(
    file: UploadFile = File(...),
    lang: str = "rus+eng",
    doc_type: Optional[str] = None,
    priority_speed: bool = False,
):
    """Загружает документ и выполняет OCR."""
    doc_id = str(uuid.uuid4())
    suffix = Path(file.filename).suffix.lower()
    save_path = UPLOAD_DIR / f"{doc_id}{suffix}"

    content = await file.read()
    save_path.write_bytes(content)

    model_info = select_ocr_model(
        document_path=save_path,
        lang=lang.split("+")[0],
        doc_type=doc_type,
        priority_speed=priority_speed,
    )

    if suffix == ".pdf":
        pages = _process_pdf(save_path, lang)
    else:
        text, conf = _run_tesseract_ocr(save_path, lang)
        pages = [{"page": 1, "text": text, "confidence": conf, "engine": "tesseract"}]

    save_path.unlink(missing_ok=True)

    avg_conf = sum(p["confidence"] for p in pages) / len(pages) if pages else 0.0

    return JSONResponse({
        "document_id": doc_id,
        "filename": file.filename,
        "model_used": model_info["model"],
        "engine": model_info["engine"],
        "pages": pages,
        "avg_confidence": round(avg_conf, 4),
        "status": "completed",
    })


@app.post("/ocr/select-model")
def select_model(
    lang: str = "ru",
    doc_type: Optional[str] = None,
    priority_speed: bool = False,
):
    """Возвращает рекомендуемую модель без обработки файла."""
    result = select_ocr_model(lang=lang, doc_type=doc_type, priority_speed=priority_speed)
    return result


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
