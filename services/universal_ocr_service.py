"""
Universal OCR Service — обработка любых документов.
"""

import os
import logging
from typing import List, Dict, Optional, Any
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum

import numpy as np
from PIL import Image
import fitz

from core import (
    get_vlm_manager,
    OCREnsemble,
    OCResult,
    preprocess_for_ocr,
)

logger = logging.getLogger(__name__)


class ProcessingMode(Enum):
    """Режимы обработки."""
    FAST = "fast"           # Только Tesseract
    STANDARD = "standard"   # Tesseract + EasyOCR
    ACCURATE = "accurate"   # + VLM


@dataclass
class OCRPageResult:
    """Результат OCR одной страницы."""
    page_num: int
    text: str
    confidence: float
    engine: str
    processing_time: float = 0.0


@dataclass
class OCRDocumentResult:
    """Результат OCR документа."""
    source_file: str
    pages: List[OCRPageResult]
    mode: str

    @property
    def full_text(self) -> str:
        """Полный текст всех страниц."""
        return "\n\n".join(p.text for p in self.pages)

    @property
    def avg_confidence(self) -> float:
        """Средняя уверенность."""
        if not self.pages:
            return 0.0
        return sum(p.confidence for p in self.pages) / len(self.pages)

    def to_excel_row(self) -> Dict[str, Any]:
        """Конвертация в строку Excel."""
        return {
            "Файл": self.source_file,
            "Страниц": len(self.pages),
            "Режим": self.mode,
            "Средняя уверенность": f"{self.avg_confidence:.0%}",
            "Текст (первые 1000 симв)": self.full_text[:1000],
        }


class UniversalOCRService:
    """
    Универсальный OCR сервис.
    Поддерживает PDF, изображения, разные режимы точности.
    """

    def __init__(
        self,
        default_mode: ProcessingMode = ProcessingMode.STANDARD,
        tesseract_path: Optional[str] = None,
    ):
        self.default_mode = default_mode
        self.ensemble = OCREnsemble(tesseract_path=tesseract_path)
        self.vlm = get_vlm_manager()

        logger.info("UniversalOCRService инициализирован (режим: %s)", default_mode.value)

    def process_file(
        self,
        file_path: str,
        mode: Optional[ProcessingMode] = None,
        doc_type_hint: Optional[str] = None,
    ) -> OCRDocumentResult:
        """
        Обработка файла.

        Args:
            file_path: Путь к файлу
            mode: Режим обработки
            doc_type_hint: Подсказка о типе документа

        Returns:
            OCRDocumentResult
        """
        mode = mode or self.default_mode
        path = Path(file_path)

        if not path.exists():
            return OCRDocumentResult(
                source_file=path.name,
                pages=[],
                mode=mode.value,
            )

        suffix = path.suffix.lower()

        if suffix == '.pdf':
            return self._process_pdf(file_path, mode, doc_type_hint)
        elif suffix in ('.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.gif'):
            return self._process_image(file_path, mode, doc_type_hint)
        else:
            logger.warning("Неподдерживаемый формат: %s", suffix)
            return OCRDocumentResult(
                source_file=path.name,
                pages=[],
                mode=mode.value,
            )

    def _process_pdf(
        self,
        pdf_path: str,
        mode: ProcessingMode,
        doc_type_hint: Optional[str],
    ) -> OCRDocumentResult:
        """Обработка PDF."""
        pages = []
        path = Path(pdf_path)

        try:
            doc = fitz.open(pdf_path)

            for page_num in range(len(doc)):
                page = doc[page_num]

                # Пробуем нативный текст
                native_text = page.get_text().strip()

                if len(native_text) > 100 and mode != ProcessingMode.ACCURATE:
                    # Достаточно текста, используем нативный
                    pages.append(OCRPageResult(
                        page_num=page_num + 1,
                        text=native_text,
                        confidence=1.0,
                        engine="native",
                    ))
                else:
                    # Нужен OCR
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                    img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                        pix.height, pix.width, pix.n)

                    page_result = self._ocr_image_array(img_array, mode, doc_type_hint)
                    page_result.page_num = page_num + 1
                    pages.append(page_result)

            doc.close()

        except Exception as e:
            logger.error("Ошибка обработки PDF: %s", e)

        return OCRDocumentResult(
            source_file=path.name,
            pages=pages,
            mode=mode.value,
        )

    def _process_image(
        self,
        image_path: str,
        mode: ProcessingMode,
        doc_type_hint: Optional[str],
    ) -> OCRDocumentResult:
        """Обработка изображения."""
        path = Path(image_path)

        try:
            img = Image.open(image_path).convert('RGB')
            img_array = np.array(img)

            page_result = self._ocr_image_array(img_array, mode, doc_type_hint)
            page_result.page_num = 1

        except Exception as e:
            logger.error("Ошибка обработки изображения: %s", e)
            page_result = OCRPageResult(
                page_num=1,
                text="",
                confidence=0.0,
                engine="error",
            )

        return OCRDocumentResult(
            source_file=path.name,
            pages=[page_result],
            mode=mode.value,
        )

    def _ocr_image_array(
        self,
        img_array: np.ndarray,
        mode: ProcessingMode,
        doc_type_hint: Optional[str],
    ) -> OCRPageResult:
        """OCR массива изображения."""
        import time
        start_time = time.time()

        if mode == ProcessingMode.FAST:
            # Только Tesseract
            result = self.ensemble.tesseract.recognize(img_array)

        elif mode == ProcessingMode.STANDARD:
            # Ансамбль Tesseract + EasyOCR
            result = self.ensemble.recognize(img_array, mode="best")

        else:  # ACCURATE
            # + VLM
            base_result = self.ensemble.recognize(img_array, mode="best")

            try:
                vlm_result = self.vlm.extract_document_text(
                    Image.fromarray(img_array),
                    doc_type_hint
                )

                # Объединяем
                result = OCResult(
                    text=vlm_result.text or base_result.text,
                    confidence=vlm_result.confidence,
                    engine="vlm+ensemble",
                )
            except Exception as e:
                logger.warning("VLM ошибка: %s", e)
                result = base_result

        return OCRPageResult(
            page_num=0,
            text=result.text,
            confidence=result.confidence,
            engine=result.engine,
            processing_time=time.time() - start_time,
        )

    def process_batch(
        self,
        folder_path: str,
        mode: Optional[ProcessingMode] = None,
        progress_callback=None,
    ) -> List[OCRDocumentResult]:
        """
        Пакетная обработка папки.

        Args:
            folder_path: Путь к папке
            mode: Режим обработки
            progress_callback: Функция (current, total, filename)

        Returns:
            Список результатов
        """
        path = Path(folder_path)

        # Собираем файлы
        files = []
        for ext in ('*.pdf', '*.png', '*.jpg', '*.jpeg', '*.tiff', '*.bmp'):
            files.extend(path.glob(ext))

        results = []
        total = len(files)

        for i, file_path in enumerate(files):
            if progress_callback:
                progress_callback(i, total, file_path.name)

            result = self.process_file(str(file_path), mode)
            results.append(result)

        if progress_callback:
            progress_callback(total, total, "Готово!")

        return results

    def export_to_excel(self, results: List[OCRDocumentResult], output_path: str):
        """Экспорт в Excel."""
        import pandas as pd

        # Основная информация по документам
        doc_rows = [r.to_excel_row() for r in results]

        # Детальная информация по страницам
        page_rows = []
        for doc in results:
            for page in doc.pages:
                page_rows.append({
                    "Файл": doc.source_file,
                    "Страница": page.page_num,
                    "Текст": page.text[:2000],  # Ограничиваем
                    "Уверенность": f"{page.confidence:.0%}",
                    "Движок": page.engine,
                })

        # Запись в Excel с двумя листами
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            pd.DataFrame(doc_rows).to_excel(writer, sheet_name='Документы', index=False)
            pd.DataFrame(page_rows).to_excel(writer, sheet_name='Страницы', index=False)

        logger.info("Экспортировано в %s", output_path)

    def get_status(self) -> Dict[str, Any]:
        """Статус сервиса."""
        return {
            "engines": self.ensemble.get_status(),
            "vlm_loaded": self.vlm.is_loaded(),
            "default_mode": self.default_mode.value,
        }