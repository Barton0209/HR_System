# ocr_core/main.py
"""
OCR Core Service v3.0
Движки: Tesseract (основной) + EasyOCR (резервный/ансамбль)
Предобработка: deskew + moire removal + CLAHE(LAB) + text sharpening
Порт: 8001
"""
import os
import uuid
import logging
from pathlib import Path
from typing import Optional

import fitz
import numpy as np
import cv2
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="IDPS OCR Core", version="3.0.0", docs_url="/docs")

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "/tmp/idps_ocr"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

TESSERACT_PATH = os.getenv("TESSERACT_PATH", "/usr/bin/tesseract")

# -----------------------------------------------------------------------
# Инициализация движков (ленивая)
# -----------------------------------------------------------------------

TESSERACT_OK = False
_easyocr_reader = None   # загружается по требованию

try:
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
    pytesseract.get_tesseract_version()
    TESSERACT_OK = True
    logger.info("Tesseract OK: %s", TESSERACT_PATH)
except Exception as e:
    logger.warning("Tesseract недоступен: %s", e)


def _get_easyocr(langs: list[str]):
    """Ленивая загрузка EasyOCR — только при первом вызове."""
    global _easyocr_reader
    if _easyocr_reader is None:
        try:
            import easyocr
            _easyocr_reader = easyocr.Reader(langs, gpu=False, verbose=False)
            logger.info("EasyOCR загружен: %s", langs)
        except ImportError:
            logger.warning("EasyOCR не установлен")
    return _easyocr_reader


# -----------------------------------------------------------------------
# Предобработка (из OCR_DOC_UP + OCR_PASS_UP)
# -----------------------------------------------------------------------

def _deskew(img: np.ndarray) -> np.ndarray:
    """Коррекция перекоса через преобразование Хафа."""
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if len(img.shape) == 3 else img
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLines(edges, 1, np.pi / 180, threshold=100)
    if lines is not None and len(lines) > 3:
        angles = []
        for line in lines[:20]:
            rho, theta = line[0]
            angle = np.degrees(theta) - 90
            if -45 < angle < 45:
                angles.append(angle)
        if angles:
            median_angle = float(np.median(angles))
            if abs(median_angle) > 0.5:
                h, w = img.shape[:2]
                M = cv2.getRotationMatrix2D((w // 2, h // 2), median_angle, 1.0)
                return cv2.warpAffine(img, M, (w, h),
                                      flags=cv2.INTER_CUBIC,
                                      borderMode=cv2.BORDER_REPLICATE)
    return img


def _remove_moire(img: np.ndarray) -> np.ndarray:
    """Подавление муара через FFT-фильтрацию."""
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if len(img.shape) == 3 else img
    dft = np.fft.fftshift(np.fft.fft2(gray))
    magnitude = np.log(np.abs(dft) + 1)
    h, w = magnitude.shape
    cy, cx = h // 2, w // 2
    y, x = np.ogrid[:h, :w]
    dist = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    lo, hi = int(min(h, w) * 0.05), int(min(h, w) * 0.15)
    band = (dist > lo) & (dist < hi)
    if magnitude[band].mean() > magnitude.mean() * 2.5:
        mask = np.ones_like(dft, dtype=np.float32)
        mask[band] = 0.3
        result = np.real(np.fft.ifft2(np.fft.ifftshift(dft * mask))).astype(np.uint8)
        result = cv2.bilateralFilter(result, 5, 30, 30)
        return cv2.cvtColor(result, cv2.COLOR_GRAY2RGB) if len(img.shape) == 3 else result
    return img


def _sharpen_text(img: np.ndarray) -> np.ndarray:
    """Избирательное повышение резкости текстовых областей."""
    kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if len(img.shape) == 3 else img
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, text_mask = cv2.threshold(cv2.subtract(gray, blur), 15, 255, cv2.THRESH_BINARY)
    text_mask = cv2.dilate(text_mask, np.ones((2, 2), np.uint8)) / 255.0
    sharpened = cv2.filter2D(img, -1, kernel)
    if len(img.shape) == 3:
        m = cv2.cvtColor(text_mask.astype(np.float32), cv2.COLOR_GRAY2RGB) * 0.3
        return np.clip(img * (1 - m) + sharpened * m, 0, 255).astype(np.uint8)
    return np.clip(img * (1 - text_mask * 0.3) + sharpened * (text_mask * 0.3), 0, 255).astype(np.uint8)


def _preprocess(img: np.ndarray) -> np.ndarray:
    """Полный пайплайн: deskew → moire → CLAHE(LAB) → sharpen → binarize."""
    img = _deskew(img)
    img = _remove_moire(img)
    if len(img.shape) == 3:
        lab = cv2.cvtColor(img, cv2.COLOR_RGB2LAB)
        l, a, b = cv2.split(lab)
        l = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(l)
        img = cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2RGB)
    else:
        img = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(img)
    img = _sharpen_text(img)
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if len(img.shape) == 3 else img
    gray = cv2.medianBlur(gray, 3)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return binary


# -----------------------------------------------------------------------
# OCR движки
# -----------------------------------------------------------------------

def _ocr_tesseract(img_array: np.ndarray, lang: str) -> tuple[str, float]:
    """Tesseract OCR с предобработкой."""
    if not TESSERACT_OK:
        return "", 0.0
    try:
        from PIL import Image as PILImage
        binary = _preprocess(img_array)
        pil = PILImage.fromarray(binary)
        data = pytesseract.image_to_data(
            pil, lang=lang, config="--psm 6 --oem 3",
            output_type=pytesseract.Output.DICT
        )
        text = pytesseract.image_to_string(pil, lang=lang, config="--psm 6 --oem 3")
        confs = [int(c) for c in data["conf"]
                 if str(c).lstrip('-').isdigit() and int(c) >= 0]
        conf = round(sum(confs) / len(confs) / 100, 4) if confs else 0.0
        return text, conf
    except Exception as e:
        logger.error("Tesseract error: %s", e)
        return "", 0.0


def _ocr_easyocr(img_array: np.ndarray, lang: str) -> tuple[str, float]:
    """EasyOCR — резервный движок."""
    # Маппинг языков Tesseract → EasyOCR
    lang_map = {
        "rus": ["ru"], "eng": ["en"],
        "rus+eng": ["ru", "en"], "en": ["en"], "ru": ["ru"],
    }
    easy_langs = lang_map.get(lang, ["ru", "en"])
    reader = _get_easyocr(easy_langs)
    if reader is None:
        return "", 0.0
    try:
        # EasyOCR принимает BGR
        if len(img_array.shape) == 3:
            bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        else:
            bgr = img_array
        results = reader.readtext(bgr)
        if not results:
            return "", 0.0
        texts = [r[1] for r in results]
        confs = [r[2] for r in results]
        text = "\n".join(texts)
        conf = round(sum(confs) / len(confs), 4)
        return text, conf
    except Exception as e:
        logger.error("EasyOCR error: %s", e)
        return "", 0.0


def _ocr_ensemble(img_array: np.ndarray, lang: str) -> tuple[str, float, str]:
    """
    Ансамбль: Tesseract + EasyOCR.
    Возвращает лучший результат по уверенности.
    """
    t_text, t_conf = _ocr_tesseract(img_array, lang)
    e_text, e_conf = _ocr_easyocr(img_array, lang)

    # Если оба дали результат — берём с большей уверенностью
    if t_text and e_text:
        if t_conf >= e_conf:
            return t_text, t_conf, "tesseract"
        return e_text, e_conf, "easyocr"
    if t_text:
        return t_text, t_conf, "tesseract"
    if e_text:
        return e_text, e_conf, "easyocr"
    return "", 0.0, "none"


# -----------------------------------------------------------------------
# Обработка документов
# -----------------------------------------------------------------------

def _process_pdf(path: Path, lang: str, use_ensemble: bool) -> list[dict]:
    results = []
    try:
        doc = fitz.open(str(path))
        for i, page in enumerate(doc):
            native = page.get_text().strip()
            if len(native) > 50:
                results.append({
                    "page": i + 1, "text": native,
                    "confidence": 1.0, "engine": "native"
                })
            else:
                pix = page.get_pixmap(matrix=fitz.Matrix(3, 3), alpha=False)
                arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                    pix.height, pix.width, pix.n)
                if use_ensemble:
                    text, conf, engine = _ocr_ensemble(arr, lang)
                else:
                    text, conf = _ocr_tesseract(arr, lang)
                    engine = "tesseract"
                results.append({
                    "page": i + 1, "text": text,
                    "confidence": conf, "engine": engine
                })
        doc.close()
    except Exception as e:
        logger.error("PDF error: %s", e)
    return results


def _process_image(path: Path, lang: str, use_ensemble: bool) -> list[dict]:
    try:
        img = cv2.imread(str(path))
        if img is None:
            return []
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        if use_ensemble:
            text, conf, engine = _ocr_ensemble(rgb, lang)
        else:
            text, conf = _ocr_tesseract(rgb, lang)
            engine = "tesseract"
        return [{"page": 1, "text": text, "confidence": conf, "engine": engine}]
    except Exception as e:
        logger.error("Image error: %s", e)
        return []


# -----------------------------------------------------------------------
# API
# -----------------------------------------------------------------------

@app.get("/health")
def health():
    easyocr_ok = False
    try:
        import easyocr  # noqa
        easyocr_ok = True
    except ImportError:
        pass
    return {
        "status": "ok",
        "service": "ocr-core",
        "version": "3.0.0",
        "engines": {
            "tesseract": TESSERACT_OK,
            "easyocr": easyocr_ok,
        }
    }


@app.post("/ocr/process")
async def process_document(
    file: UploadFile = File(...),
    lang: str = "rus+eng",
    ensemble: bool = False,
):
    """
    Распознавание текста из PDF или изображения.

    - **lang**: язык OCR (rus+eng, eng, rus, ...)
    - **ensemble**: использовать ансамбль Tesseract+EasyOCR (медленнее, точнее)
    """
    doc_id = str(uuid.uuid4())
    suffix = Path(file.filename or "file.pdf").suffix.lower()
    if suffix not in (".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp"):
        raise HTTPException(400, f"Неподдерживаемый формат: {suffix}")

    save_path = UPLOAD_DIR / f"{doc_id}{suffix}"
    save_path.write_bytes(await file.read())

    if suffix == ".pdf":
        pages = _process_pdf(save_path, lang, ensemble)
    else:
        pages = _process_image(save_path, lang, ensemble)

    save_path.unlink(missing_ok=True)

    avg_conf = round(sum(p["confidence"] for p in pages) / len(pages), 4) if pages else 0.0
    engines_used = list({p["engine"] for p in pages})

    return JSONResponse({
        "document_id": doc_id,
        "filename": file.filename,
        "pages": pages,
        "page_count": len(pages),
        "avg_confidence": avg_conf,
        "lang": lang,
        "ensemble": ensemble,
        "engines_used": engines_used,
    })


@app.post("/ocr/select-engine")
def select_engine(
    lang: str = "rus+eng",
    doc_type: Optional[str] = None,
    priority_speed: bool = False,
):
    """Рекомендует движок без обработки файла."""
    if priority_speed or not _get_easyocr.__doc__:
        engine = "tesseract"
        reason = "приоритет скорости"
    elif doc_type in ("passport", "паспорт"):
        engine = "ensemble"
        reason = "паспорт — максимальная точность"
    elif lang not in ("rus+eng", "eng", "rus"):
        engine = "easyocr"
        reason = "нестандартный язык"
    else:
        engine = "tesseract"
        reason = "стандартный документ"
    return {"engine": engine, "reason": reason, "lang": lang}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001, reload=True)
