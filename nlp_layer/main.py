# nlp_layer/main.py
"""
NLP Layer Service — извлечение сущностей и классификация документов.
"""

import re
import logging
from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="IDPS NLP Layer", version="2.0.0")

# --- Паттерны для извлечения сущностей ---
DATE_RE = re.compile(r'\b(\d{1,2})[./](\d{1,2})[./](\d{2,4})\b')
PHONE_RE = re.compile(r'(?:\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}')
FIO_RE = re.compile(r'[А-ЯЁ][а-яё]{2,}\s+[А-ЯЁ][а-яё]{2,}\s+[А-ЯЁ][а-яё]{4,}')
PASSPORT_RU_RE = re.compile(r'\b(\d{4})\s+(\d{6})\b')
PASSPORT_FOREIGN_RE = re.compile(r'\b([A-Z]{1,3})\s*(\d{6,9})\b')

DOC_CLASSES = {
    "заявка на приобретение билетов": "ticket_request",
    "счет": "invoice",
    "договор": "contract",
    "акт": "act",
    "паспорт": "passport",
}

REASON_MAP = [
    (r'увольнени',          'Увольнение'),
    (r'межвахт|межвахтов',  'Межвахтовый отдых'),
    (r'командировк',        'Командировка'),
    (r'трудоустройств|устройств', 'Устройство на работу'),
    (r'перевод',            'Перевод в др. ОП'),
    (r'больничн|болезн',    'Больничный'),
    (r'отпуск',             'Ежегодный отпуск'),
]


class NLPRequest(BaseModel):
    text: str
    doc_type: Optional[str] = None


def classify_document(text: str) -> tuple[str, float]:
    text_lower = text.lower()
    for keyword, cls in DOC_CLASSES.items():
        if keyword in text_lower:
            return cls, 0.9
    return "unknown", 0.5


def extract_entities(text: str) -> list[dict]:
    entities = []

    # ФИО
    for m in FIO_RE.finditer(text):
        entities.append({"type": "fio", "text": m.group(0), "offset": [m.start(), m.end()]})

    # Даты
    for m in DATE_RE.finditer(text):
        d, mo, y = m.groups()
        if len(y) == 2:
            y = "20" + y
        entities.append({
            "type": "date",
            "text": m.group(0),
            "normalized": f"{d.zfill(2)}.{mo.zfill(2)}.{y}",
            "offset": [m.start(), m.end()]
        })

    # Телефоны
    for m in PHONE_RE.finditer(text):
        entities.append({"type": "phone", "text": m.group(0), "offset": [m.start(), m.end()]})

    # Паспорт РФ
    for m in PASSPORT_RU_RE.finditer(text):
        entities.append({
            "type": "passport_ru",
            "series": m.group(1),
            "number": m.group(2),
            "offset": [m.start(), m.end()]
        })

    # Иностранный паспорт
    for m in PASSPORT_FOREIGN_RE.finditer(text):
        entities.append({
            "type": "passport_foreign",
            "series": m.group(1),
            "number": m.group(2),
            "offset": [m.start(), m.end()]
        })

    # Обоснование (для заявок на билеты)
    text_lower = text.lower()
    for pattern, label in REASON_MAP:
        if re.search(pattern, text_lower):
            entities.append({"type": "reason", "text": label})
            break

    return entities


@app.get("/health")
def health():
    return {"status": "ok", "service": "nlp-layer"}


@app.post("/nlp/process")
def process_text(request: NLPRequest):
    doc_class, confidence = classify_document(request.text)
    entities = extract_entities(request.text)

    return {
        "doc_class": doc_class,
        "doc_class_conf": confidence,
        "entities": entities,
        "entity_count": len(entities),
    }


@app.post("/nlp/extract-ticket")
def extract_ticket_data(request: NLPRequest):
    """Специализированное извлечение данных для заявок на билеты."""
    entities = extract_entities(request.text)

    fio_list = [e["text"] for e in entities if e["type"] == "fio"]
    dates = [e["normalized"] for e in entities if e["type"] == "date"]
    phones = [e["text"] for e in entities if e["type"] == "phone"]
    reasons = [e["text"] for e in entities if e["type"] == "reason"]

    passport_series, passport_num = "", ""
    for e in entities:
        if e["type"] in ("passport_ru", "passport_foreign"):
            passport_series = e.get("series", "")
            passport_num = e.get("number", "")
            break

    return {
        "fio": fio_list[0] if fio_list else "",
        "dates": dates,
        "phone": phones[0] if phones else "",
        "reason": reasons[0] if reasons else "",
        "passport_series": passport_series,
        "passport_num": passport_num,
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
