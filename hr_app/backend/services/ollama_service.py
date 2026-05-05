"""
Ollama Service — интеграция с локальными AI моделями
"""
import base64
import json
import logging
import os
from pathlib import Path
from typing import Optional, Dict

import httpx

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


async def check_ollama() -> Dict:
    """Проверяет доступность Ollama и список моделей."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                models = [m["name"] for m in data.get("models", [])]
                return {"available": True, "models": models}
    except Exception as e:
        logger.debug("Ollama not available: %s", e)
    return {"available": False, "models": []}


async def ocr_image_with_ollama(
    image_path: str,
    model: str = "glm-ocr:latest",
    prompt: str = None
) -> Optional[str]:
    """
    OCR изображения через Ollama vision model.
    Поддерживает glm-ocr:latest и qwen2.5vl:latest
    """
    if not prompt:
        prompt = (
            "Извлеки весь текст с этого документа. "
            "Верни структурированный JSON с полями: "
            "фамилия, имя, отчество, дата_рождения, серия_паспорта, "
            "номер_паспорта, дата_выдачи, кем_выдан, место_рождения, пол. "
            "Если поле не найдено — пустая строка."
        )

    try:
        image_data = Path(image_path).read_bytes()
        image_b64 = base64.b64encode(image_data).decode()

        payload = {
            "model": model,
            "prompt": prompt,
            "images": [image_b64],
            "stream": False,
            "options": {"temperature": 0.1}
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json=payload
            )
            if resp.status_code == 200:
                result = resp.json()
                return result.get("response", "")
            else:
                logger.error("Ollama OCR error: %s", resp.text)
                return None

    except Exception as e:
        logger.exception("Ollama OCR failed for %s", image_path)
        return None


async def parse_passport_text(text: str, model: str = "qwen2.5-coder:1.5b") -> Dict:
    """Парсит текст паспорта через LLM."""
    prompt = f"""Из следующего текста OCR извлеки данные паспорта в JSON формате.
Поля: surname, name, patronymic, birth_date (ДД.ММ.ГГГГ), gender, birth_place,
      series, number, issue_date (ДД.ММ.ГГГГ), issuer, issuer_code, expiry_date.
Верни ТОЛЬКО JSON, без пояснений.

Текст OCR:
{text}
"""
    try:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.0}
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload)
            if resp.status_code == 200:
                response_text = resp.json().get("response", "")
                # Extract JSON from response
                start = response_text.find("{")
                end = response_text.rfind("}") + 1
                if start >= 0 and end > start:
                    return json.loads(response_text[start:end])
    except Exception as e:
        logger.exception("Passport parse failed")
    return {}


async def analyze_document(image_path: str, doc_type: str = "auto") -> Dict:
    """
    Универсальный анализ документа.
    doc_type: auto | passport_ru | passport_foreign | work_permit | visa
    """
    prompts = {
        "passport_ru": (
            "Это российский паспорт. Извлеки: фамилию, имя, отчество, "
            "дату рождения (ДД.ММ.ГГГГ), серию и номер, дату выдачи, "
            "кем выдан, место рождения, пол. Верни JSON."
        ),
        "passport_foreign": (
            "Это иностранный паспорт/документ. Извлеки MRZ строки если есть, "
            "фамилию, имя, дату рождения, гражданство, номер документа, "
            "срок действия. Верни JSON."
        ),
        "visa": (
            "Это виза или разрешение на работу. Извлеки: тип документа, "
            "номер, дату выдачи, срок действия, имя владельца. Верни JSON."
        ),
        "auto": (
            "Определи тип документа и извлеки все возможные данные: "
            "ФИО, даты, номера документов, серии, кем выдан. "
            "Верни JSON с полями: doc_type, данные документа."
        )
    }

    prompt = prompts.get(doc_type, prompts["auto"])

    # Try glm-ocr first (best for Russian docs)
    status = await check_ollama()
    models = status.get("models", [])

    ocr_model = "glm-ocr:latest"
    if "glm-ocr:latest" not in models and models:
        ocr_model = models[0]

    raw_text = await ocr_image_with_ollama(image_path, model=ocr_model, prompt=prompt)
    if not raw_text:
        return {"error": "OCR недоступен", "raw": ""}

    # Try to parse JSON
    result = {"raw": raw_text}
    try:
        start = raw_text.find("{")
        end = raw_text.rfind("}") + 1
        if start >= 0 and end > start:
            parsed = json.loads(raw_text[start:end])
            result.update(parsed)
    except json.JSONDecodeError:
        pass

    return result
