# ocr_pipeline/runner.py
"""
Оркестратор OCR пайплайна.

Режимы:
  Mode.PASSPORT  — паспорта (РФ + иностранные)
  Mode.DOCUMENT  — общие документы (PDF-сканы, JPEG)
"""

import logging
import os
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
from enum import Enum
from pathlib import Path

import fitz
import numpy as np
from PIL import Image as PILImage

from .preprocessor import preprocess_for_passport, preprocess_for_ocr, pil_to_numpy
from .passport_mode import parse_passport_ru, parse_passport_foreign
from .document_mode import ocr_document, extract_native_pdf, available_engines

logger = logging.getLogger(__name__)

TESSERACT_PATH = os.getenv(
    "TESSERACT_PATH",
    r"C:\Users\DerevyankoGA\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
)

_TESS_OK = False
try:
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
    pytesseract.get_tesseract_version()
    _TESS_OK = True
except Exception:
    pass


class Mode(Enum):
    PASSPORT = "passport"
    DOCUMENT = "document"


# ── Извлечение текста (паспортный режим) ──────────────────────────────────────

def _ocr_img_passport(img: np.ndarray, lang: str = "rus+eng") -> str:
    if not _TESS_OK:
        return ""
    try:
        binary = preprocess_for_passport(img)
        pil = PILImage.fromarray(binary)
        return pytesseract.image_to_string(pil, lang=lang, config="--psm 6 --oem 3")
    except Exception as e:
        logger.error("Passport OCR: %s", e)
        return ""


def _get_text_passport(path: Path, lang: str = "rus") -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        try:
            doc = fitz.open(str(path))
            pages = []
            for page in doc:
                native = page.get_text().strip()
                if len(native) > 40:
                    pages.append(native)
                elif _TESS_OK:
                    pix = page.get_pixmap(matrix=fitz.Matrix(3, 3), alpha=False)
                    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                        pix.height, pix.width, pix.n).copy()  # copy() освобождает pix
                    del pix
                    pages.append(_ocr_img_passport(arr, lang))
                    del arr
            doc.close()
            return "\n".join(pages)
        except Exception as e:
            logger.error("PDF passport %s: %s", path.name, e)
            return ""
    elif suffix in (".jpg", ".jpeg", ".png", ".tiff", ".bmp"):
        try:
            arr = pil_to_numpy(PILImage.open(str(path)).convert("RGB"))
            result = _ocr_img_passport(arr, lang)
            del arr
            return result
        except Exception as e:
            logger.error("Image passport %s: %s", path.name, e)
            return ""
    return ""


# ── Извлечение текста (документный режим) ─────────────────────────────────────

def _get_text_document(path: Path, lang_tess: str = "rus+eng") -> dict:
    suffix = path.suffix.lower()

    # E1: нативный PDF
    if suffix == ".pdf":
        native = extract_native_pdf(str(path))
        if native:
            return {"text": native, "engines": ["native_pdf"]}

    # Рендерим в изображения
    images = []
    if suffix == ".pdf":
        try:
            doc = fitz.open(str(path))
            for page in doc:
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                    pix.height, pix.width, pix.n)
                images.append(arr)
            doc.close()
        except Exception as e:
            logger.error("PDF render %s: %s", path.name, e)
    elif suffix in (".jpg", ".jpeg", ".png", ".tiff", ".bmp"):
        try:
            images.append(pil_to_numpy(PILImage.open(str(path)).convert("RGB")))
        except Exception as e:
            logger.error("Image load %s: %s", path.name, e)

    if not images:
        return {"text": "", "engines": []}

    all_texts, all_engines = [], set()
    for img in images:
        preprocessed = preprocess_for_ocr(img)
        result = ocr_document(preprocessed, lang_tess=lang_tess)
        if result["text"].strip():
            all_texts.append(result["text"])
        all_engines.update(result["engines"])

    return {"text": "\n\n".join(all_texts), "engines": list(all_engines)}


# ── Публичные функции ─────────────────────────────────────────────────────────

def run_passport(path: Path, fio: str = "",
                 is_foreign: bool = False, lang: str = "rus") -> dict:
    """Обрабатывает один файл паспорта."""
    logger.info("[PASSPORT] %s", path.name)
    text = _get_text_passport(path, lang)
    if not text.strip():
        logger.warning("Пустой текст: %s", path.name)
        return None

    img_path = str(path) if path.suffix.lower() in (".jpg", ".jpeg", ".png") else None
    data = (parse_passport_foreign if is_foreign else parse_passport_ru)(
        text, fio, img_path
    )
    data["_file"]   = path.name
    data["_mode"]   = "passport"
    data["_source"] = "foreign" if is_foreign else "ru"
    return data


def run_document(path: Path, lang_tess: str = "rus+eng") -> dict:
    """Обрабатывает один документ."""
    logger.info("[DOCUMENT] %s", path.name)
    result = _get_text_document(path, lang_tess)
    result["_file"] = path.name
    result["_mode"] = "document"
    return result


def run_batch(items: list, mode: Mode) -> list:
    """
    Пакетная обработка.
    items для PASSPORT: [{"path", "fio", "source", "lang"}]
    items для DOCUMENT: [{"path"}]
    """
    import gc
    engines = available_engines()
    logger.info("Режим: %s | Движки: %s", mode.value,
                engines if mode == Mode.DOCUMENT else ["Tesseract+MRZ"])
    logger.info("Файлов: %d", len(items))

    records, errors = [], []
    for item in items:
        path = item["path"]
        try:
            if mode == Mode.PASSPORT:
                rec = run_passport(
                    path,
                    fio=item.get("fio", ""),
                    is_foreign=item.get("source") == "Иностранные",
                    lang=item.get("lang", "rus"),
                )
            else:
                rec = run_document(path)
            if rec:
                records.append(rec)
        except Exception as e:
            logger.error("Ошибка %s: %s", path.name, e)
            errors.append(path.name)
        finally:
            gc.collect()  # освобождаем память после каждого файла

    logger.info("Обработано: %d | Ошибок: %d", len(records), len(errors))
    return records
