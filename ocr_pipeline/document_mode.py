# ocr_pipeline/document_mode.py
"""
Режим 2: DOCUMENT
=================
Ансамблевое OCR для общих документов (PDF-сканы, JPEG).

Порядок методов:
  E1. PyMuPDF native  — нативный текст (мгновенно, если PDF векторный)
  E2. PaddleOCR       — PP-OCRv4, лучший детектор таблиц
  E3. EasyOCR         — CRAFT + CRNN, устойчив к изогнутому тексту
  E4. Tesseract 5.x   — референсный движок, быстрый
  E5. Голосование     — Levenshtein-выравнивание + выбор лучшего по confidence
"""

import re
import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# ── Опциональные движки ───────────────────────────────────────────────────────

_PADDLE_OK = False
try:
    import os as _os
    _os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    from paddleocr import PaddleOCR as _PaddleOCR
    _paddle_instance = None
    _PADDLE_OK = True
except ImportError:
    pass

_EASY_OK = False
try:
    import easyocr as _easyocr
    _easy_instance = None
    _EASY_OK = True
except ImportError:
    pass

_TESS_OK = False
try:
    import pytesseract as _pytesseract
    import os
    _pytesseract.pytesseract.tesseract_cmd = os.getenv(
        "TESSERACT_PATH",
        r"C:\Users\DerevyankoGA\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
    )
    _pytesseract.get_tesseract_version()
    _TESS_OK = True
except Exception:
    pass


def _get_paddle(lang: str = "ru") -> Optional[object]:
    global _paddle_instance
    if not _PADDLE_OK:
        return None
    if _paddle_instance is None:
        try:
            _paddle_instance = _PaddleOCR(
                use_angle_cls=True, lang=lang,
                use_gpu=False, show_log=False
            )
        except Exception as e:
            logger.warning("PaddleOCR init error: %s", e)
            return None
    return _paddle_instance


def _get_easy(lang: list = None) -> Optional[object]:
    global _easy_instance
    if not _EASY_OK:
        return None
    if _easy_instance is None:
        try:
            _easy_instance = _easyocr.Reader(
                lang or ['ru', 'en'], gpu=False, verbose=False
            )
        except Exception as e:
            logger.warning("EasyOCR init error: %s", e)
            return None
    return _easy_instance


# ── E1: PyMuPDF нативный текст ───────────────────────────────────────────────

def extract_native_pdf(path: str) -> str:
    """Извлекает нативный текст из PDF (работает только для векторных PDF)."""
    try:
        import fitz
        doc = fitz.open(path)
        pages = [page.get_text() for page in doc]
        doc.close()
        text = "\n".join(pages).strip()
        return text if len(text) > 50 else ""
    except Exception as e:
        logger.debug("Native PDF error: %s", e)
        return ""


# ── E2: PaddleOCR ─────────────────────────────────────────────────────────────

def ocr_paddle(img: np.ndarray, lang: str = "ru") -> tuple:
    """
    Возвращает (text, confidence).
    confidence — среднее по всем блокам.
    """
    paddle = _get_paddle(lang)
    if paddle is None:
        return "", 0.0
    try:
        result = paddle.ocr(img, cls=True)
        if not result or not result[0]:
            return "", 0.0
        lines, scores = [], []
        for line in result[0]:
            if line and len(line) >= 2:
                text_info = line[1]
                if isinstance(text_info, (list, tuple)) and len(text_info) >= 2:
                    lines.append(str(text_info[0]))
                    scores.append(float(text_info[1]))
        text = "\n".join(lines)
        conf = sum(scores) / len(scores) if scores else 0.0
        return text, conf
    except Exception as e:
        logger.debug("PaddleOCR error: %s", e)
        return "", 0.0


# ── E3: EasyOCR ───────────────────────────────────────────────────────────────

def ocr_easy(img: np.ndarray, lang: list = None) -> tuple:
    """Возвращает (text, confidence)."""
    reader = _get_easy(lang)
    if reader is None:
        return "", 0.0
    try:
        result = reader.readtext(img, detail=1, paragraph=False)
        if not result:
            return "", 0.0
        lines, scores = [], []
        for (_, text, conf) in result:
            lines.append(text)
            scores.append(conf)
        text = "\n".join(lines)
        conf = sum(scores) / len(scores) if scores else 0.0
        return text, conf
    except Exception as e:
        logger.debug("EasyOCR error: %s", e)
        return "", 0.0


# ── E4: Tesseract ─────────────────────────────────────────────────────────────

def ocr_tesseract(img: np.ndarray, lang: str = "rus+eng") -> tuple:
    """Возвращает (text, confidence)."""
    if not _TESS_OK:
        return "", 0.0
    try:
        from PIL import Image as PILImage
        pil = PILImage.fromarray(img)
        data = _pytesseract.image_to_data(
            pil, lang=lang, config="--psm 6 --oem 3",
            output_type=_pytesseract.Output.DICT
        )
        words, confs = [], []
        for word, conf in zip(data['text'], data['conf']):
            if word.strip() and int(conf) > 0:
                words.append(word)
                confs.append(int(conf))
        text = " ".join(words)
        conf = sum(confs) / len(confs) / 100.0 if confs else 0.0
        return text, conf
    except Exception as e:
        logger.debug("Tesseract error: %s", e)
        return "", 0.0


# ── E5: Голосование ───────────────────────────────────────────────────────────

def _levenshtein(a: str, b: str) -> int:
    """Расстояние Левенштейна между двумя строками."""
    if len(a) < len(b):
        a, b = b, a
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            curr.append(min(prev[j + 1] + 1, curr[j] + 1,
                            prev[j] + (ca != cb)))
        prev = curr
    return prev[-1]


def ensemble_vote(results: list) -> str:
    """
    Голосование по результатам нескольких движков.
    results: список (text, confidence)
    Возвращает текст с наибольшей суммарной поддержкой.
    """
    # Фильтруем пустые
    valid = [(t, c) for t, c in results if t.strip()]
    if not valid:
        return ""
    if len(valid) == 1:
        return valid[0][0]

    # Выбираем текст с наибольшим confidence
    # Если confidence близки (< 0.05 разница) — берём более длинный
    valid.sort(key=lambda x: x[1], reverse=True)
    best_text, best_conf = valid[0]
    for text, conf in valid[1:]:
        if best_conf - conf < 0.05 and len(text) > len(best_text):
            best_text = text
    return best_text


# ── Публичный интерфейс ───────────────────────────────────────────────────────

def ocr_document(img: np.ndarray, lang_tess: str = "rus+eng",
                 lang_paddle: str = "ru",
                 lang_easy: list = None) -> dict:
    """
    Запускает все доступные движки и возвращает ансамблевый результат.

    Возвращает:
      {
        "text":    str,   # итоговый текст (лучший из движков)
        "results": dict,  # тексты от каждого движка
        "engines": list,  # какие движки сработали
      }
    """
    results = {}
    engines = []

    # E2: PaddleOCR
    if _PADDLE_OK:
        text, conf = ocr_paddle(img, lang_paddle)
        if text.strip():
            results["paddle"] = (text, conf)
            engines.append(f"paddle(conf={conf:.2f})")

    # E3: EasyOCR
    if _EASY_OK:
        text, conf = ocr_easy(img, lang_easy or ['ru', 'en'])
        if text.strip():
            results["easy"] = (text, conf)
            engines.append(f"easy(conf={conf:.2f})")

    # E4: Tesseract
    if _TESS_OK:
        text, conf = ocr_tesseract(img, lang_tess)
        if text.strip():
            results["tesseract"] = (text, conf)
            engines.append(f"tess(conf={conf:.2f})")

    # E5: Голосование
    best_text = ensemble_vote(list(results.values()))

    return {
        "text":    best_text,
        "results": {k: v[0] for k, v in results.items()},
        "engines": engines,
    }


def available_engines() -> list:
    """Возвращает список доступных OCR движков."""
    engines = []
    if _PADDLE_OK:
        engines.append("PaddleOCR")
    if _EASY_OK:
        engines.append("EasyOCR")
    if _TESS_OK:
        engines.append("Tesseract")
    return engines
