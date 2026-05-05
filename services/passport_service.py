"""
Passport Service — обработка паспортов 23 стран.
Использует core библиотеки.
"""

import os
import logging
from typing import List, Dict, Optional, Any
from pathlib import Path
from dataclasses import dataclass, asdict

import numpy as np
from PIL import Image
import fitz  # PyMuPDF

from core import (
    get_vlm_manager,
    extract_mrz_from_text,
    mrz_to_dict,
    TesseractEngine,
    preprocess_for_ocr,
    get_country_by_iso3,
    get_country_by_mrz_code,
    CountryConfig,
)

logger = logging.getLogger(__name__)


@dataclass
class PassportResult:
    """Результат обработки паспорта."""
    source_file: str
    page_num: int = 1

    # Обнаруженная страна
    country_iso3: Optional[str] = None
    country_name: Optional[str] = None

    # MRZ данные
    mrz_data: Optional[Dict] = None
    mrz_valid: bool = False

    # VLM данные
    vlm_data: Optional[Dict] = None
    vlm_used: bool = False

    # Объединённые данные (MRZ + VLM)
    surname: Optional[str] = None
    given_names: Optional[str] = None
    doc_number: Optional[str] = None
    nationality: Optional[str] = None
    dob: Optional[str] = None
    sex: Optional[str] = None
    expiry: Optional[str] = None
    issuing_authority: Optional[str] = None

    # Метаданные
    processing_time: float = 0.0
    confidence: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Конвертация в словарь."""
        return asdict(self)

    def to_excel_row(self) -> Dict[str, Any]:
        """Конвертация в строку для Excel."""
        return {
            "Файл": self.source_file,
            "Страница": self.page_num,
            "Страна": self.country_name or self.country_iso3 or "",
            "Фамилия": self.surname or "",
            "Имена": self.given_names or "",
            "Номер документа": self.doc_number or "",
            "Гражданство": self.nationality or "",
            "Дата рождения": self.dob or "",
            "Пол": self.sex or "",
            "Срок действия": self.expiry or "",
            "Кем выдан": self.issuing_authority or "",
            "MRZ валиден": "Да" if self.mrz_valid else "Нет",
            "VLM использован": "Да" if self.vlm_used else "Нет",
            "Уверенность": f"{self.confidence:.0%}",
        }


class PassportService:
    """
    Сервис обработки паспортов.
    Комбинирует MRZ + OCR + VLM для максимальной точности.
    """

    def __init__(self, use_vlm: bool = True, tesseract_path: Optional[str] = None):
        self.use_vlm = use_vlm
        self.tesseract = TesseractEngine(tesseract_path)
        self.vlm = get_vlm_manager() if use_vlm else None

        logger.info("PassportService инициализирован (VLM: %s)", use_vlm)

    def process_image(
        self,
        image_path: str,
        country_hint: Optional[str] = None,
        use_vlm: Optional[bool] = None,
    ) -> PassportResult:
        """
        Обработка изображения паспорта.

        Args:
            image_path: Путь к изображению
            country_hint: Подсказка о стране (ISO3)
            use_vlm: Переопределить использование VLM

        Returns:
            PassportResult
        """
        import time
        start_time = time.time()

        path = Path(image_path)
        result = PassportResult(source_file=path.name)

        try:
            # Загрузка изображения
            img = Image.open(image_path).convert('RGB')
            img_array = np.array(img)

            # Шаг 1: OCR для извлечения текста и MRZ
            ocr_result = self.tesseract.recognize(img_array, lang="eng")

            # Шаг 2: Извлечение MRZ
            mrz = extract_mrz_from_text(ocr_result.text)
            if mrz:
                result.mrz_data = mrz_to_dict(mrz)
                result.mrz_valid = mrz.mrz_valid

                # Определение страны по MRZ
                country = get_country_by_mrz_code(mrz.country)
                if country:
                    result.country_iso3 = country.iso3
                    result.country_name = country.name_ru

            # Шаг 3: VLM если включен и нужен
            should_use_vlm = use_vlm if use_vlm is not None else self.use_vlm

            if should_use_vlm and self.vlm:
                try:
                    vlm_country = result.country_iso3 or country_hint
                    result.vlm_data = self.vlm.extract_passport_data(img, vlm_country)
                    result.vlm_used = True
                except Exception as e:
                    logger.warning("VLM ошибка: %s", e)

            # Шаг 4: Объединение данных
            self._merge_data(result, mrz, result.vlm_data)

            # Расчёт уверенности
            result.confidence = self._calculate_confidence(result, mrz)

        except Exception as e:
            logger.error("Ошибка обработки паспорта: %s", e)
            result.error = str(e)

        result.processing_time = time.time() - start_time
        return result

    def process_pdf(
        self,
        pdf_path: str,
        country_hint: Optional[str] = None,
        use_vlm: Optional[bool] = None,
    ) -> List[PassportResult]:
        """
        Обработка PDF с паспортами.

        Returns:
            Список результатов по страницам
        """
        results = []
        path = Path(pdf_path)

        try:
            doc = fitz.open(pdf_path)

            for page_num in range(len(doc)):
                page = doc[page_num]

                # Рендеринг страницы
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                    pix.height, pix.width, pix.n)

                # Временное сохранение
                temp_path = f"/tmp/passport_page_{page_num}.png"
                Image.fromarray(img_array).save(temp_path)

                # Обработка
                result = self.process_image(temp_path, country_hint, use_vlm)
                result.source_file = f"{path.name} (стр. {page_num + 1})"
                result.page_num = page_num + 1
                results.append(result)

                # Очистка
                os.remove(temp_path)

            doc.close()

        except Exception as e:
            logger.error("Ошибка обработки PDF: %s", e)
            # Возвращаем результат с ошибкой
            results.append(PassportResult(
                source_file=path.name,
                error=str(e)
            ))

        return results

    def process_batch(
        self,
        file_paths: List[str],
        country_hint: Optional[str] = None,
        progress_callback=None,
    ) -> List[PassportResult]:
        """
        Пакетная обработка файлов.

        Args:
            file_paths: Список путей к файлам
            country_hint: Подсказка о стране
            progress_callback: Функция (current, total, filename)

        Returns:
            Список результатов
        """
        results = []
        total = len(file_paths)

        for i, file_path in enumerate(file_paths):
            if progress_callback:
                progress_callback(i, total, Path(file_path).name)

            if file_path.lower().endswith('.pdf'):
                page_results = self.process_pdf(file_path, country_hint)
                results.extend(page_results)
            else:
                result = self.process_image(file_path, country_hint)
                results.append(result)

        if progress_callback:
            progress_callback(total, total, "Готово!")

        return results

    def _merge_data(
        self,
        result: PassportResult,
        mrz: Optional[Any],
        vlm_data: Optional[Dict],
    ):
        """Объединение данных из MRZ и VLM."""
        # Приоритет MRZ для номера документа и дат (точнее)
        if mrz:
            result.doc_number = mrz.doc_num
            result.dob = mrz.dob
            result.expiry = mrz.expiry
            result.sex = mrz.sex
            result.nationality = mrz.nationality

            # ФИО из MRZ
            if mrz.surname:
                result.surname = mrz.surname
            if mrz.given_names:
                result.given_names = mrz.given_names

        # VLM дополняет или исправляет
        if vlm_data:
            # ФИО из VLM если MRZ не уверен
            if not result.surname and vlm_data.get('surname'):
                result.surname = vlm_data['surname']
            if not result.given_names and vlm_data.get('given_names'):
                result.given_names = vlm_data['given_names']

            # Кем выдан (только VLM)
            if vlm_data.get('issuing_authority'):
                result.issuing_authority = vlm_data['issuing_authority']

            # Исправление ошибок MRZ если VLM уверен
            vlm_conf = vlm_data.get('_vlm_metadata', {}).get('confidence', 0)
            if vlm_conf > 0.8:
                if vlm_data.get('doc_number') and not result.doc_number:
                    result.doc_number = vlm_data['doc_number']

    def _calculate_confidence(self, result: PassportResult, mrz: Optional[Any]) -> float:
        """Расчёт общей уверенности."""
        scores = []

        # MRZ уверенность
        if mrz:
            scores.append(mrz.confidence)

        # VLM уверенность
        if result.vlm_data and '_vlm_metadata' in result.vlm_data:
            scores.append(result.vlm_data['_vlm_metadata'].get('confidence', 0))

        # Наличие ключевых полей
        field_score = 0
        if result.surname:
            field_score += 0.1
        if result.doc_number:
            field_score += 0.2
        if result.dob:
            field_score += 0.1
        scores.append(min(field_score, 0.5))

        return sum(scores) / len(scores) if scores else 0.0

    def export_to_excel(self, results: List[PassportResult], output_path: str):
        """Экспорт результатов в Excel."""
        import pandas as pd

        rows = [r.to_excel_row() for r in results]
        df = pd.DataFrame(rows)
        df.to_excel(output_path, index=False)
        logger.info("Экспортировано %d записей в %s", len(results), output_path)

    def get_status(self) -> Dict[str, Any]:
        """Статус сервиса."""
        return {
            "tesseract_available": self.tesseract.is_available(),
            "vlm_available": self.vlm.is_loaded() if self.vlm else False,
            "vlm_enabled": self.use_vlm,
        }