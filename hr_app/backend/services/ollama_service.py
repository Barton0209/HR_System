"""
Ollama Service — интеграция с локальными AI моделями + Tesseract fallback
"""
import base64
import json
import logging
import os
import re
from pathlib import Path
from typing import Optional, Dict, Any

import httpx

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Tesseract fallback (работает без root прав через pip)
try:
    import pytesseract
    from PIL import Image
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    logger.info("pytesseract не установлен — используется только Ollama")


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


def ocr_with_tesseract(image_path: str, lang: str = "rus+eng") -> Optional[str]:
    """
    Fallback OCR через Tesseract (работает локально без интернета).
    Требует установленный tesseract в системе или pytesseract.
    """
    if not TESSERACT_AVAILABLE:
        return None
    try:
        img = Image.open(image_path)
        # Предобработка для улучшения качества
        text = pytesseract.image_to_string(img, lang=lang)
        return text.strip() if text else None
    except Exception as e:
        logger.warning("Tesseract OCR failed: %s", e)
        return None


def parse_passport_with_regex(text: str) -> Dict[str, Any]:
    """
    Парсит текст паспорта через регулярные выражения (fallback без AI).
    Работает для российских паспортов.
    """
    result = {
        "surname": "", "name": "", "patronymic": "",
        "birth_date": "", "gender": "", "birth_place": "",
        "series": "", "number": "", "issue_date": "",
        "issuer": "", "expiry_date": ""
    }
    
    # Серия и номер: 4 цифры пробел 6 цифр
    passport_match = re.search(r'(\d{4})\s*(\d{6})', text)
    if passport_match:
        result["series"] = passport_match.group(1)
        result["number"] = passport_match.group(2)
    
    # Дата рождения: ДД.ММ.ГГГГ или ДД ММ ГГГГ
    date_match = re.search(r'(\d{1,2})[.\s](\d{1,2})[.\s](\d{4})', text)
    if date_match:
        result["birth_date"] = f"{date_match.group(1):0>2}.{date_match.group(2):0>2}.{date_match.group(3)}"
    
    # Пол: Мужской/Женский или М/Ж (проверяем до даты рождения)
    gender_text = text[:300]  # Берём первые 300 символов для надёжности
    if re.search(r'[Мм]уж|[^\w]М[^\w]|пол.*?[Мм]', gender_text):
        result["gender"] = "М"
    elif re.search(r'[Жж]ен|[^\w]Ж[^\w]|пол.*?[Жж]', gender_text):
        result["gender"] = "Ж"
    
    # Фамилия (после слова Фамилия:)
    surname_match = re.search(r'[Фф][аА][мM][иИ][лL][иИ][яЯ]\s*[:\-]?\s*([А-ЯЁA-Z][а-яёa-z]+)', text)
    if surname_match:
        result["surname"] = surname_match.group(1)
    
    # Имя
    name_match = re.search(r'[Ии][мM][яЯ]\s*[:\-]?\s*([А-ЯЁA-Z][а-яёa-z]+)', text)
    if name_match:
        result["name"] = name_match.group(1)
    
    # Отчество
    patronymic_match = re.search(r'[Оо][тT][чЧ][еЕ][сС][тT][вВ][оО]\s*[:\-]?\s*([А-ЯЁA-Z][а-яёa-z]+)', text)
    if patronymic_match:
        result["patronymic"] = patronymic_match.group(1)
    
    # Кем выдан (длинная строка после "Кем выдан")
    issuer_match = re.search(r'[Кк][еЕ][мM]\s+[Вв][ыЫ][дД][аА][нН]+\s*[:\-]?\s*(.+?)(?=\d{2}\.\d{2}\.\d{4}|$)', text, re.DOTALL)
    if issuer_match:
        result["issuer"] = issuer_match.group(1).strip()
    
    return result


async def ocr_image_with_ollama(
    image_path: str,
    model: str = "glm-ocr:latest",
    prompt: str = None
) -> Optional[str]:
    """
    OCR изображения через Ollama vision model.
    Поддерживает glm-ocr:latest и qwen2.5vl:latest
    Fallback на Tesseract если Ollama недоступен.
    """
    if not prompt:
        prompt = (
            "Извлеки весь текст с этого документа. "
            "Верни структурированный JSON с полями: "
            "фамилия, имя, отчество, дата_рождения, серия_паспорта, "
            "номер_паспорта, дата_выдачи, кем_выдан, место_рождения, пол. "
            "Если поле не найдено — пустая строка."
        )

    # Сначала пробуем Ollama
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

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json=payload
            )
            if resp.status_code == 200:
                result = resp.json()
                return result.get("response", "")
            else:
                logger.warning("Ollama OCR error: %s", resp.text)
    except Exception as e:
        logger.debug("Ollama unavailable, trying Tesseract: %s", e)

    # Fallback на Tesseract
    tesseract_text = ocr_with_tesseract(image_path)
    if tesseract_text:
        logger.info("Tesseract OCR successful")
        return tesseract_text
    
    logger.error("All OCR methods failed for %s", image_path)
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
    
    Работает полностью локально:
    1. Ollama (если доступен) — лучшее качество
    2. Tesseract + regex parsing — fallback без интернета
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

    # Проверяем доступность Ollama
    status = await check_ollama()
    models = status.get("models", [])
    
    ocr_model = "glm-ocr:latest" if "glm-ocr:latest" in models else (models[0] if models else None)
    
    raw_text = None
    
    # Пробуем Ollama если доступен
    if ocr_model:
        logger.info("Using Ollama model: %s", ocr_model)
        raw_text = await ocr_image_with_ollama(image_path, model=ocr_model, prompt=prompt)
    
    # Если Ollama не дал результат, используем Tesseract
    if not raw_text and TESSERACT_AVAILABLE:
        logger.info("Falling back to Tesseract OCR")
        raw_text = ocr_with_tesseract(image_path)
        
        # Парсим через regex для российских паспортов
        if raw_text and doc_type == "passport_ru":
            parsed = parse_passport_with_regex(raw_text)
            if any(parsed.values()):  # Если что-то найдено
                return {
                    "source": "tesseract+regex",
                    "raw": raw_text,
                    **parsed
                }
    
    if not raw_text:
        return {"error": "OCR недоступен (Ollama и Tesseract не работают)", "raw": ""}

    # Пытаемся распарсить JSON из ответа
    result = {"raw": raw_text, "source": "ollama" if ocr_model else "tesseract"}
    try:
        start = raw_text.find("{")
        end = raw_text.rfind("}") + 1
        if start >= 0 and end > start:
            parsed = json.loads(raw_text[start:end])
            result.update(parsed)
    except json.JSONDecodeError:
        # Если не JSON, пробуем regex парсинг
        if doc_type == "passport_ru":
            parsed = parse_passport_with_regex(raw_text)
            if any(parsed.values()):
                result.update(parsed)
    
    return result
