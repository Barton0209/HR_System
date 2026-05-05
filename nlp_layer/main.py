# nlp_layer/main.py
"""
NLP Layer — извлечение структурированных данных из текста документов.
Поддерживает: паспорт РФ, иностранный паспорт, заявка на билеты, произвольный документ.
Порт: 8002
"""
import re
import logging
from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="IDPS NLP Layer", version="2.0.0", docs_url="/docs")

# ── Паттерны ──────────────────────────────────────────────────────────────────

DATE_RE    = re.compile(r'\b(\d{1,2})[./](\d{1,2})[./](\d{2,4})\b')
PHONE_RE   = re.compile(r'(?:\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}')
EMAIL_RE   = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')
FIO_RE     = re.compile(r'[А-ЯЁ][а-яё]{2,}\s+[А-ЯЁ][а-яё]{2,}\s+[А-ЯЁ][а-яё]{4,}')
SNILS_RE   = re.compile(r'\b\d{3}[-\s]?\d{3}[-\s]?\d{3}[-\s]?\d{2}\b')
INN_RE     = re.compile(r'\b\d{10,12}\b')

# Паспорт РФ: серия 4 цифры + номер 6 цифр
PASSPORT_RU_RE      = re.compile(r'\b(\d{2}\s?\d{2})\s+(\d{6})\b')
# Иностранный: буквы + цифры
PASSPORT_FOREIGN_RE = re.compile(r'\b([A-Z]{1,3})\s*(\d{6,9})\b')

# Классификация документов
DOC_SIGNATURES = {
    "passport_ru":      ["паспорт гражданина", "российской федерации", "серия", "выдан"],
    "passport_foreign": ["passport", "passeport", "загранпаспорт"],
    "ticket_request":   ["заявка на приобретение билетов", "маршрут", "пункт отправления"],
    "invoice":          ["счёт", "счет на оплату", "итого", "ндс"],
    "contract":         ["договор", "соглашение", "стороны", "предмет договора"],
    "act":              ["акт", "выполненных работ", "приёма-передачи"],
    "snils":            ["страховой номер", "снилс", "пенсионного"],
    "inn":              ["идентификационный номер налогоплательщика", "инн"],
}

REASON_MAP = [
    (r'увольнени',                         'Увольнение'),
    (r'межвахт|межвахтов',                 'Межвахтовый отдых'),
    (r'командировк',                       'Командировка'),
    (r'трудоустройств|устройств',          'Устройство на работу'),
    (r'перевод',                           'Перевод в др. ОП'),
    (r'больничн|болезн',                   'Больничный'),
    (r'отпуск',                            'Ежегодный отпуск'),
]

CITIZENSHIP_KEYWORDS = {
    'РОССИЯ': ['россия', 'российская федерация', 'russia', 'rf'],
    'КАЗАХСТАН': ['казахстан', 'kazakhstan', 'kz'],
    'УЗБЕКИСТАН': ['узбекистан', 'uzbekistan', 'uz'],
    'КИРГИЗИЯ': ['киргизия', 'кыргызстан', 'kyrgyzstan', 'kg'],
    'ТАДЖИКИСТАН': ['таджикистан', 'tajikistan', 'tj'],
    'БЕЛАРУСЬ': ['беларусь', 'белоруссия', 'belarus', 'by'],
    'УКРАИНА': ['украина', 'ukraine', 'ua'],
    'АРМЕНИЯ': ['армения', 'armenia', 'am'],
    'АЗЕРБАЙДЖАН': ['азербайджан', 'azerbaijan', 'az'],
    'ГРУЗИЯ': ['грузия', 'georgia', 'ge'],
}


# ── Схемы запросов ────────────────────────────────────────────────────────────

class NLPRequest(BaseModel):
    text: str
    doc_type: Optional[str] = None   # подсказка, если известен тип


# ── Вспомогательные функции ───────────────────────────────────────────────────

def _normalize_date(d: str, m: str, y: str) -> str:
    if len(y) == 2:
        y = "20" + y
    return f"{d.zfill(2)}.{m.zfill(2)}.{y}"


def classify_document(text: str) -> tuple[str, float]:
    """Определяет тип документа по ключевым словам."""
    text_lower = text.lower()
    scores: dict[str, int] = {}
    for doc_type, keywords in DOC_SIGNATURES.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score:
            scores[doc_type] = score
    if not scores:
        return "unknown", 0.3
    best = max(scores, key=scores.__getitem__)
    conf = min(0.5 + scores[best] * 0.15, 0.99)
    return best, round(conf, 2)


def extract_fio(text: str) -> list[str]:
    exclude = {'общество', 'ответствен', 'заявка', 'компании', 'должность',
               'руководитель', 'специалист', 'сотрудник', 'кадрам', 'административный'}
    result = []
    for m in FIO_RE.finditer(text):
        fio = m.group(0).strip()
        if not any(w in fio.lower() for w in exclude):
            result.append(fio)
    return result


def extract_dates(text: str) -> list[dict]:
    results = []
    for m in DATE_RE.finditer(text):
        d, mo, y = m.groups()
        normalized = _normalize_date(d, mo, y)
        year = int(y) if len(y) == 4 else 2000 + int(y)
        # Определяем тип даты по контексту (50 символов до)
        ctx = text[max(0, m.start() - 50): m.start()].lower()
        if any(w in ctx for w in ('рожд', 'birth', 'born', 'дата рожд')):
            dtype = 'birth_date'
        elif any(w in ctx for w in ('выдан', 'issued', 'дата выдачи')):
            dtype = 'issue_date'
        elif any(w in ctx for w in ('действ', 'valid', 'окончани', 'expir')):
            dtype = 'expiry_date'
        elif any(w in ctx for w in ('вылет', 'отправл', 'departure')):
            dtype = 'flight_date'
        else:
            dtype = 'birth_date' if 1950 <= year <= 2010 else 'date'
        results.append({"type": dtype, "raw": m.group(0), "normalized": normalized})
    return results


def extract_passport(text: str) -> dict:
    # Российский
    m = PASSPORT_RU_RE.search(text)
    if m:
        series = m.group(1).replace(' ', '')
        return {"type": "passport_ru", "series": series, "number": m.group(2)}
    # Иностранный
    m = PASSPORT_FOREIGN_RE.search(text)
    if m:
        return {"type": "passport_foreign", "series": m.group(1), "number": m.group(2)}
    # Только номер
    m = re.search(r'\b(\d{7,9})\b', text)
    if m:
        return {"type": "passport_foreign", "series": "", "number": m.group(1)}
    return {}


def extract_citizenship(text: str) -> str:
    text_lower = text.lower()
    for country, keywords in CITIZENSHIP_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return country
    return ""


def extract_address(text: str) -> str:
    patterns = [
        r'(?:адрес|прописк[аи]|зарегистрирован[а]?\s+по)[:\s]+([^\n]{10,120})',
        r'(?:г\.|город|ул\.|улица|пр\.|проспект)\s+[^\n]{5,100}',
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(0).strip()
    return ""


def extract_snils(text: str) -> str:
    m = SNILS_RE.search(text)
    return m.group(0) if m else ""


def extract_reason(text: str) -> str:
    text_lower = text.lower()
    scores: dict[str, int] = {}
    for pattern, label in REASON_MAP:
        count = len(re.findall(pattern, text_lower))
        if count:
            scores[label] = count
    return max(scores, key=scores.__getitem__) if scores else ""


def extract_cities(text: str) -> list[str]:
    """Извлекает города из текста (для маршрутов)."""
    CITIES = [
        'санкт-петербург', 'петербург', 'москва', 'фергана', 'ташкент',
        'бишкек', 'алматы', 'астана', 'душанбе', 'ашхабад', 'ереван',
        'минск', 'краснодар', 'екатеринбург', 'новосибирск', 'казань',
        'сочи', 'адлер', 'мурманск', 'норильск', 'якутск', 'хабаровск',
        'владивосток', 'иркутск', 'тюмень', 'уфа', 'самара', 'омск',
    ]
    text_lower = text.lower()
    found = []
    for city in CITIES:
        if city in text_lower and city not in found:
            found.append(city.title())
    return found


# ── Эндпоинты ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "nlp-layer"}


@app.post("/nlp/classify")
def classify(request: NLPRequest):
    """Только классификация документа."""
    doc_class, conf = classify_document(request.text)
    return {"doc_class": doc_class, "confidence": conf}


@app.post("/nlp/process")
def process_text(request: NLPRequest):
    """Полная обработка: классификация + все сущности."""
    text = request.text
    doc_class, conf = classify_document(text)

    entities = {
        "fio":         extract_fio(text),
        "dates":       extract_dates(text),
        "phones":      PHONE_RE.findall(text),
        "emails":      EMAIL_RE.findall(text),
        "passport":    extract_passport(text),
        "citizenship": extract_citizenship(text),
        "address":     extract_address(text),
        "snils":       extract_snils(text),
        "cities":      extract_cities(text),
        "reason":      extract_reason(text),
    }

    return {
        "doc_class":   doc_class,
        "confidence":  conf,
        "entities":    entities,
    }


@app.post("/nlp/passport")
def extract_passport_data(request: NLPRequest):
    """
    Специализированное извлечение данных паспорта.
    Возвращает структурированный объект паспортных данных.
    """
    text = request.text
    fio_list = extract_fio(text)
    dates    = extract_dates(text)
    passport = extract_passport(text)
    citizenship = extract_citizenship(text)
    address  = extract_address(text)

    birth_date  = next((d["normalized"] for d in dates if d["type"] == "birth_date"), "")
    issue_date  = next((d["normalized"] for d in dates if d["type"] == "issue_date"), "")
    expiry_date = next((d["normalized"] for d in dates if d["type"] == "expiry_date"), "")

    # Кем выдан — ищем после «выдан»
    issuer = ""
    m = re.search(r'(?:выдан[а]?|issued\s+by)[:\s]+([^\n]{5,120})', text, re.IGNORECASE)
    if m:
        issuer = m.group(1).strip()

    return {
        "fio":          fio_list[0] if fio_list else "",
        "birth_date":   birth_date,
        "citizenship":  citizenship,
        "doc_series":   passport.get("series", ""),
        "doc_number":   passport.get("number", ""),
        "doc_type":     passport.get("type", ""),
        "issue_date":   issue_date,
        "expiry_date":  expiry_date,
        "issuer":       issuer,
        "address":      address,
        "phones":       PHONE_RE.findall(text),
        "snils":        extract_snils(text),
    }


@app.post("/nlp/ticket")
def extract_ticket_data(request: NLPRequest):
    """Специализированное извлечение данных заявки на билеты."""
    text = request.text
    fio_list = extract_fio(text)
    dates    = extract_dates(text)
    cities   = extract_cities(text)
    phones   = PHONE_RE.findall(text)
    passport = extract_passport(text)

    flight_dates = [d["normalized"] for d in dates if d["type"] == "flight_date"]
    all_dates    = [d["normalized"] for d in dates]

    route1 = f"{cities[0]} - {cities[1]}" if len(cities) >= 2 else ""
    route2 = f"{cities[1]} - {cities[0]}" if len(cities) >= 2 else ""

    return {
        "fio":          fio_list[0] if fio_list else "",
        "route":        route1,
        "route2":       route2,
        "date":         flight_dates[0] if flight_dates else (all_dates[1] if len(all_dates) > 1 else ""),
        "date2":        flight_dates[1] if len(flight_dates) > 1 else (all_dates[2] if len(all_dates) > 2 else ""),
        "reason":       extract_reason(text),
        "phone":        phones[0] if phones else "",
        "doc_series":   passport.get("series", ""),
        "doc_number":   passport.get("number", ""),
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002, reload=True)
