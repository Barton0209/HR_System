"""
OCR Engines — обертки для Tesseract и EasyOCR.
"""

import logging
from typing import Optional, Tuple, List, Dict
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from core.preprocessing import preprocess_for_ocr

logger = logging.getLogger(__name__)


@dataclass
class OCResult:
    """Результат OCR."""
    text: str
    confidence: float
    engine: str
    error: Optional[str] = None


class TesseractEngine:
    """Движок Tesseract OCR."""

    def __init__(self, tesseract_path: Optional[str] = None):
        self.tesseract_path = tesseract_path
        self._available = False
        self._check_availability()

    def _check_availability(self):
        """Проверка доступности Tesseract."""
        try:
            import pytesseract

            if self.tesseract_path:
                pytesseract.pytesseract.tesseract_cmd = self.tesseract_path

            # Проверка версии
            version = pytesseract.get_tesseract_version()
            logger.info("Tesseract доступен: %s", version)
            self._available = True

        except Exception as e:
            logger.warning("Tesseract недоступен: %s", e)
            self._available = False

    def is_available(self) -> bool:
        return self._available

    def recognize(
        self,
        image: np.ndarray,
        lang: str = "rus+eng",
        preprocess: bool = True,
    ) -> OCResult:
        """
        Распознавание текста.

        Args:
            image: numpy array (RGB)
            lang: язык(и) Tesseract
            preprocess: применить предобработку

        Returns:
            OCResult
        """
        if not self._available:
            return OCResult("", 0.0, "tesseract", "Tesseract not available")

        try:
            import pytesseract
            from PIL import Image as PILImage

            # Предобработка
            if preprocess:
                processed = preprocess_for_ocr(image)
            else:
                processed = image

            # Конвертация в PIL
            if len(processed.shape) == 2:
                pil_img = PILImage.fromarray(processed, mode='L')
            else:
                pil_img = PILImage.fromarray(processed)

            # OCR
            text = pytesseract.image_to_string(
                pil_img,
                lang=lang,
                config='--psm 6 --oem 3'
            )

            # Оценка уверенности
            data = pytesseract.image_to_data(
                pil_img,
                lang=lang,
                config='--psm 6 --oem 3',
                output_type=pytesseract.Output.DICT
            )

            confs = [
                int(c) for c in data["conf"]
                if str(c).lstrip('-').isdigit() and int(c) >= 0
            ]
            confidence = sum(confs) / len(confs) / 100 if confs else 0.5

            return OCResult(
                text=text.strip(),
                confidence=round(confidence, 4),
                engine="tesseract"
            )

        except Exception as e:
            logger.error("Tesseract ошибка: %s", e)
            return OCResult("", 0.0, "tesseract", str(e))


class EasyOCREngine:
    """Движок EasyOCR."""

    def __init__(self, languages: Optional[List[str]] = None):
        self.languages = languages or ['ru', 'en']
        self._reader = None
        self._available = False

    def _get_reader(self):
        """Ленивая загрузка EasyOCR."""
        if self._reader is None:
            try:
                import easyocr
                logger.info("Загрузка EasyOCR: %s", self.languages)
                self._reader = easyocr.Reader(
                    self.languages,
                    gpu=False,  # CPU по умолчанию
                    verbose=False
                )
                self._available = True
            except ImportError:
                logger.warning("EasyOCR не установлен")
                self._available = False
        return self._reader

    def is_available(self) -> bool:
        if self._reader is not None:
            return self._available
        # Проверка без загрузки
        try:
            import easyocr
            return True
        except ImportError:
            return False

    def recognize(
        self,
        image: np.ndarray,
        preprocess: bool = True,
    ) -> OCResult:
        """
        Распознавание текста.

        Args:
            image: numpy array (RGB)
            preprocess: применить предобработку

        Returns:
            OCResult
        """
        reader = self._get_reader()
        if reader is None:
            return OCResult("", 0.0, "easyocr", "EasyOCR not available")

        try:
            # Предобработка
            if preprocess:
                processed = preprocess_for_ocr(image, binarize_image=False)
            else:
                processed = image

            # EasyOCR ожидает BGR
            if len(processed.shape) == 3:
                bgr = cv2.cvtColor(processed, cv2.COLOR_RGB2BGR)
            else:
                bgr = cv2.cvtColor(processed, cv2.COLOR_GRAY2BGR)

            # OCR
            results = reader.readtext(bgr)

            if not results:
                return OCResult("", 0.0, "easyocr")

            # Объединение текста
            texts = [r[1] for r in results]
            confs = [r[2] for r in results]

            full_text = "\n".join(texts)
            avg_confidence = sum(confs) / len(confs)

            return OCResult(
                text=full_text.strip(),
                confidence=round(avg_confidence, 4),
                engine="easyocr"
            )

        except Exception as e:
            logger.error("EasyOCR ошибка: %s", e)
            return OCResult("", 0.0, "easyocr", str(e))


class OCREnsemble:
    """Ансамбль OCR движков."""

    def __init__(
        self,
        tesseract_path: Optional[str] = None,
        easyocr_languages: Optional[List[str]] = None,
    ):
        self.tesseract = TesseractEngine(tesseract_path)
        self.easyocr = EasyOCREngine(easyocr_languages)

    def recognize(
        self,
        image: np.ndarray,
        mode: str = "best",  # "tesseract", "easyocr", "best", "both"
        lang: str = "rus+eng",
    ) -> OCResult:
        """
        Распознавание с выбором лучшего результата.

        Args:
            image: numpy array (RGB)
            mode: стратегия выбора
            lang: язык для Tesseract

        Returns:
            OCResult
        """
        results = []

        # Tesseract
        if mode in ("tesseract", "best", "both"):
            tess_result = self.tesseract.recognize(image, lang)
            if tess_result.error is None:
                results.append(tess_result)

        # EasyOCR
        if mode in ("easyocr", "best", "both"):
            easy_result = self.easyocr.recognize(image)
            if easy_result.error is None:
                results.append(easy_result)

        if not results:
            return OCResult("", 0.0, "none", "No OCR engines available")

        if mode == "both":
            # Возвращаем объединённый результат
            combined_text = "\n".join(r.text for r in results if r.text)
            avg_conf = sum(r.confidence for r in results) / len(results)
            return OCResult(
                text=combined_text,
                confidence=round(avg_conf, 4),
                engine="ensemble"
            )

        # Выбираем по уверенности
        best = max(results, key=lambda r: r.confidence)
        return best

    def get_status(self) -> Dict[str, bool]:
        """Статус доступности движков."""
        return {
            "tesseract": self.tesseract.is_available(),
            "easyocr": self.easyocr.is_available(),
        }


# Утилиты

def quick_ocr(image: np.ndarray, lang: str = "rus+eng") -> str:
    """Быстрый OCR — только текст."""
    engine = TesseractEngine()
    result = engine.recognize(image, lang)
    return result.text


def accurate_ocr(image: np.ndarray, lang: str = "rus+eng") -> OCResult:
    """Точный OCR с ансамблем."""
    ensemble = OCREnsemble()
    return ensemble.recognize(image, mode="best", lang=lang)