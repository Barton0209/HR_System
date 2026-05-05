"""
VLM Manager — ленивая загрузка и управление Qwen2-VL моделью.
Один экземпляр на всё приложение.
"""

import os
import logging
import threading
from typing import Optional, Dict, Any
from dataclasses import dataclass
from pathlib import Path

import torch
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class VLMResult:
    """Результат обработки VLM."""
    text: str
    confidence: float
    device: str
    processing_time: float
    raw_output: Optional[str] = None


class VLMManager:
    """
    Менеджер VLM модели с ленивой загрузкой.
    Потокобезопасный синглтон.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._model = None
        self._processor = None
        self._device = None
        self._model_name = "Qwen/Qwen2-VL-2B-Instruct"
        self._lock = threading.Lock()
        self._initialized = True

        logger.info("VLMManager создан")

    def _get_device(self) -> str:
        """Определение оптимального устройства."""
        if torch.cuda.is_available():
            return "cuda"
        if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            return "mps"
        return "cpu"

    def load_model(self, model_name: Optional[str] = None) -> bool:
        """
        Ленивая загрузка модели.

        Returns:
            True если загрузка успешна
        """
        if self._model is not None:
            return True

        with self._lock:
            if self._model is not None:
                return True

            try:
                from transformers import Qwen2VLForConditionalGeneration, AutoProcessor

                model_name = model_name or self._model_name
                logger.info("Загрузка VLM модели %s...", model_name)

                self._device = self._get_device()
                logger.info("VLM устройство: %s", self._device)

                # Загрузка процессора
                self._processor = AutoProcessor.from_pretrained(
                    model_name,
                    trust_remote_code=True
                )

                # Загрузка модели с оптимизацией для устройства
                load_kwargs = {
                    "pretrained_model_name_or_path": model_name,
                    "trust_remote_code": True,
                }

                if self._device == "cuda":
                    load_kwargs["torch_dtype"] = torch.bfloat16
                    load_kwargs["device_map"] = "auto"
                elif self._device == "mps":
                    load_kwargs["torch_dtype"] = torch.float16
                    load_kwargs["device_map"] = "auto"
                else:
                    # CPU оптимизации
                    load_kwargs["torch_dtype"] = torch.float32
                    load_kwargs["device_map"] = "cpu"
                    load_kwargs["low_cpu_mem_usage"] = True
                    logger.warning("VLM на CPU — производительность ~15-20s/страница")

                self._model = Qwen2VLForConditionalGeneration.from_pretrained(**load_kwargs)

                logger.info("VLM модель загружена успешно")
                return True

            except Exception as e:
                logger.error("Ошибка загрузки VLM: %s", e)
                self._model = None
                self._processor = None
                return False

    def unload_model(self):
        """Выгрузка модели для освобождения памяти."""
        with self._lock:
            if self._model is not None:
                del self._model
                self._model = None
            if self._processor is not None:
                del self._processor
                self._processor = None

            if torch.cuda.is_available():
                torch.cuda.empty_cache()

            logger.info("VLM модель выгружена")

    def is_loaded(self) -> bool:
        """Проверка, загружена ли модель."""
        return self._model is not None

    def get_status(self) -> Dict[str, Any]:
        """Получение статуса VLM."""
        return {
            "loaded": self.is_loaded(),
            "device": self._device,
            "model_name": self._model_name,
            "cuda_available": torch.cuda.is_available(),
            "mps_available": hasattr(torch.backends, 'mps') and torch.backends.mps.is_available(),
        }

    def process_image(
        self,
        image: Image.Image,
        prompt: str,
        max_new_tokens: int = 2048,
        temperature: float = 0.1,
    ) -> VLMResult:
        """
        Обработка изображения через VLM.

        Args:
            image: PIL Image
            prompt: Текстовый промпт
            max_new_tokens: Максимум токенов
            temperature: Температура генерации

        Returns:
            VLMResult
        """
        import time

        start_time = time.time()

        # Убедимся что модель загружена
        if not self.load_model():
            raise RuntimeError("Не удалось загрузить VLM модель")

        with self._lock:
            # Подготовка сообщения
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "image": image},
                        {"type": "text", "text": prompt},
                    ],
                }
            ]

            # Применение шаблона чата
            text = self._processor.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True
            )

            # Подготовка входных данных
            inputs = self._processor(
                text=[text],
                images=[image],
                return_tensors="pt",
                padding=True,
            )

            # Перемещение на устройство
            inputs = {
                k: v.to(self._device) if isinstance(v, torch.Tensor) else v
                for k, v in inputs.items()
            }

            # Генерация
            with torch.no_grad():
                generated_ids = self._model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    temperature=temperature,
                    do_sample=temperature > 0,
                )

            # Декодирование
            generated_text = self._processor.batch_decode(
                generated_ids[:, inputs['input_ids'].shape[1]:],
                skip_special_tokens=True
            )[0]

            processing_time = time.time() - start_time

            # Оценка уверенности
            confidence = self._estimate_confidence(generated_text)

            return VLMResult(
                text=generated_text.strip(),
                confidence=confidence,
                device=self._device,
                processing_time=processing_time,
                raw_output=generated_text,
            )

    def _estimate_confidence(self, text: str) -> float:
        """Эвристическая оценка уверенности."""
        if not text:
            return 0.0

        score = 0.5

        # Структурированность
        if any(marker in text for marker in [":", "-", "|", ",", ";"]):
            score += 0.1

        # Наличие дат
        import re
        if re.search(r'\d{2}[./]\d{2}[./]\d{2,4}', text):
            score += 0.1

        # Разумная длина
        lines = text.strip().split('\n')
        if 3 <= len(lines) <= 100:
            score += 0.1

        # Наличие заглавных букв (имена, названия)
        if re.search(r'[A-Z]{2,}', text):
            score += 0.1

        # Штраф за мусор/Unicode артефакты
        garbage_chars = sum(1 for c in text if ord(c) > 2000)
        garbage_ratio = garbage_chars / max(len(text), 1)
        score -= garbage_ratio * 0.5

        return max(0.0, min(1.0, score))

    def extract_passport_data(
        self,
        image: Image.Image,
        country_hint: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Специализированный метод для паспортов.

        Returns:
            Словарь с полями паспорта
        """
        country_info = f" ({country_hint})" if country_hint else ""

        prompt = f"""Extract passport information from this image{country_info}.

Return a JSON object with these fields:
- surname: surname/family name
- given_names: given names (first and middle)
- doc_number: passport/document number
- nationality: nationality/citizenship
- dob: date of birth in DD.MM.YYYY format
- sex: M or F
- expiry: expiry date in DD.MM.YYYY format
- issuing_authority: who issued the passport (if visible)

Use null for fields not visible in the image.
Return ONLY the JSON object, no other text."""

        result = self.process_image(image, prompt, max_new_tokens=1024)

        # Парсинг JSON из ответа
        import json
        import re

        # Ищем JSON в ответе
        json_match = re.search(r'\{[^{}]*\}', result.text, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group())
                data["_vlm_metadata"] = {
                    "confidence": result.confidence,
                    "processing_time": result.processing_time,
                    "device": result.device,
                }
                return data
            except json.JSONDecodeError:
                pass

        # Если JSON не распарсился, возвращаем сырой результат
        return {
            "surname": None,
            "given_names": None,
            "doc_number": None,
            "nationality": None,
            "dob": None,
            "sex": None,
            "expiry": None,
            "issuing_authority": None,
            "_vlm_raw": result.text,
            "_vlm_metadata": {
                "confidence": result.confidence,
                "processing_time": result.processing_time,
                "device": result.device,
                "parse_error": True,
            }
        }

    def extract_document_text(
        self,
        image: Image.Image,
        doc_type_hint: Optional[str] = None,
    ) -> VLMResult:
        """
        Универсальное извлечение текста из документа.
        """
        type_hint = f" This appears to be a {doc_type_hint}." if doc_type_hint else ""

        prompt = f"""Extract all text from this document image.{type_hint}

Preserve the original layout and structure as much as possible.
Include all visible text, numbers, dates, and labels.
If there are tables, preserve their structure.

Return the extracted text in a clear, readable format."""

        return self.process_image(image, prompt, max_new_tokens=2048)


# Глобальный экземпляр
_vlm_manager: Optional[VLMManager] = None


def get_vlm_manager() -> VLMManager:
    """Получение глобального экземпляра VLMManager."""
    global _vlm_manager
    if _vlm_manager is None:
        _vlm_manager = VLMManager()
    return _vlm_manager


def is_vlm_available() -> bool:
    """Проверка доступности VLM (установлены ли библиотеки)."""
    try:
        from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
        return True
    except ImportError:
        return False