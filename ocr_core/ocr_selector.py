# ocr_core/ocr_selector.py
"""
Эвристический выбор OCR-модели по типу и сложности документа.
"""

import os
import yaml
import numpy as np
from pathlib import Path
from PIL import Image

CONFIG_PATH = os.getenv("OCR_CONFIG", str(Path(__file__).parent.parent / "config" / "ocr_selector.yaml"))


def load_model_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def analyze_image(document_path: Path) -> dict:
    """Вычисляет метрики изображения для выбора модели."""
    try:
        img = np.array(Image.open(document_path).convert("L"))
        h, w = img.shape[:2]
        aspect = w / h if h > 0 else 1.0
        # Высокая вариация градиента → рукописный текст
        is_handwritten_like = float(np.std(np.diff(img, axis=1))) > 40
        return {
            "height": h,
            "width": w,
            "aspect_ratio": aspect,
            "is_grayscale": True,
            "handwritten_like": is_handwritten_like,
        }
    except Exception:
        return {"height": 0, "width": 0, "aspect_ratio": 1.414,
                "is_grayscale": False, "handwritten_like": False}


def select_ocr_model(
    document_path: Path = None,
    lang: str = "ru",
    doc_type: str = None,
    priority_speed: bool = False,
    config: dict = None,
) -> dict:
    """
    Возвращает словарь:
      {'model': str, 'engine': str, 'reason': str, 'gpu_required': bool}
    """
    if config is None:
        config = load_model_config()

    meta = analyze_image(document_path) if document_path else {
        "handwritten_like": False, "aspect_ratio": 1.414
    }

    # 1. Рукописный текст
    if doc_type == "handwritten" or meta.get("handwritten_like"):
        return {
            "model": "TrOCR",
            "engine": "onnx",
            "reason": "ручной почерк (высокоточная модель)",
            "gpu_required": False,
        }

    # 2. Русский + сложный документ
    if lang in ("ru", "ru-ru") and doc_type in ("юридич_документ", "договор", "заявка"):
        return {
            "model": "Tesseract-LSTM",
            "engine": "tesseract",
            "reason": "Ru + структурированный документ",
            "gpu_required": False,
        }

    # 3. Приоритет скорости
    if priority_speed:
        return {
            "model": "Tesseract-LSTM",
            "engine": "tesseract",
            "reason": "максимальная скорость",
            "gpu_required": False,
        }

    # 4. Текстовый PDF (не скан)
    if doc_type == "textual_pdf":
        return {
            "model": "Tesseract-LSTM",
            "engine": "tesseract",
            "reason": "чистый текст PDF — быстро + стабильно",
            "gpu_required": False,
        }

    # 5. Fallback
    return {
        "model": "Tesseract-LSTM",
        "engine": "tesseract",
        "reason": "баланс скорость/точность для общего случая",
        "gpu_required": False,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("path", help="Путь к документу")
    parser.add_argument("--lang", default="ru")
    parser.add_argument("--doc_type", default=None)
    args = parser.parse_args()

    result = select_ocr_model(Path(args.path), lang=args.lang, doc_type=args.doc_type)
    print(f"Выбрана модель: {result['model']} ({result['engine']}) — {result['reason']}")
