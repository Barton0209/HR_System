# ticket_app/pdf_processor.py
"""
Обработка PDF-заявок на приобретение билетов.

Структура документа (скан):
  Строка: «ФИО ДД.ММ.ГГГГ Должность НомерПаспорта»
  Таблица маршрутов: откуда | куда | дата | транспорт
  Раздел кадров: подчёркнутое обоснование
  Телефон внизу страницы
"""

import os
import re
import logging
from typing import List, Dict, Tuple, Optional
from pathlib import Path

import fitz
import numpy as np
import cv2

from config import TESSERACT_PATH

logger = logging.getLogger(__name__)

TESSERACT_AVAILABLE = False
try:
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
    pytesseract.get_tesseract_version()
    TESSERACT_AVAILABLE = True
except Exception as e:
    logger.warning("Tesseract недоступен: %s", e)

KNOWN_CITIES = [
    'санкт-петербург', 'петербург', 'москва', 'шымкент', 'астана', 'алматы',
    'ташкент', 'бишкек', 'самарканд', 'фергана', 'наманган', 'андижан',
    'краснодар', 'екатеринбург', 'новосибирск', 'казань', 'ростов-на-дону',
    'ростов', 'сочи', 'адлер', 'астрахань', 'владивосток', 'хабаровск',
    'иркутск', 'уфа', 'пермь', 'воронеж', 'волгоград', 'самара', 'омск',
    'челябинск', 'тюмень', 'мурманск', 'архангельск', 'калининград',
    'ставрополь', 'минеральные воды', 'якутск', 'магадан', 'норильск',
    'нальчик', 'махачкала', 'грозный', 'симферополь', 'кингисепп',
    'усть-луга', 'свободный', 'тарко-сале', 'новый уренгой', 'большой камень',
    'дивноморское', 'душанбе', 'ашхабад', 'ереван', 'минск', 'белград',
    'дели', 'загреб', 'алеппо', 'дамаск', 'абакан',
]

REASON_MAP = [
    (r'увольнени',                    'Увольнение'),
    (r'межвахт|межвахтов',            'Межвахтовый отдых'),
    (r'командировк',                  'Командировка'),
    (r'трудоустройств|устройств|приём на работу', 'Устройство на работу'),
    (r'перевод',                      'Перевод в др. ОП'),
    (r'больничн|болезн',              'Больничный'),
    (r'отпуск',                       'Ежегодный отпуск'),
]

DATE_RE = re.compile(r'(\d{1,2})[./](\d{1,2})[./](\d{2,4})')
PHONE_RE = re.compile(r'(?:\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}')

_FIO_EXCLUDE = {
    'общество', 'ответствен', 'заявка', 'маршрут', 'компании', 'должность',
    'фио', 'обязан', 'заявитель', 'монтаж', 'велесстрой', 'специалист',
    'руководитель', 'сотрудник', 'кадрам', 'кадров', 'административный',
    'непосредственный', 'согласие', 'условиями',
}


def _preprocess(img_array: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)
    gray = cv2.medianBlur(gray, 3)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return binary


def _ocr_page(page: fitz.Page) -> str:
    native = page.get_text().strip()
    if len(native) > 50:
        return native
    if not TESSERACT_AVAILABLE:
        return ""
    try:
        from PIL import Image
        pix = page.get_pixmap(matrix=fitz.Matrix(3, 3), alpha=False)
        img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.height, pix.width, pix.n)
        binary = _preprocess(img_array)
        img = Image.fromarray(binary)
        return pytesseract.image_to_string(img, lang='rus+eng', config='--psm 6 --oem 3')
    except Exception as e:
        logger.error("OCR ошибка: %s", e)
        return ""


def _normalize_date(day: str, month: str, year: str) -> str:
    if len(year) == 2:
        year = "20" + year
    return f"{day.zfill(2)}.{month.zfill(2)}.{year}"


def _find_dates(text: str) -> List[str]:
    return [_normalize_date(*m) for m in DATE_RE.findall(text)]


def _title_city(city: str) -> str:
    return '-'.join(p.capitalize() for p in city.split('-'))


def _find_cities_in_line(line: str) -> List[str]:
    line_lower = line.lower()
    return [_title_city(c) for c in KNOWN_CITIES if c in line_lower]


def extract_fio(text: str) -> str:
    # Стратегия 1: ФИО + дата рождения в одной строке
    m = re.search(
        r'([А-ЯЁ][а-яёА-ЯЁ\-]{1,}\s+[А-ЯЁ][а-яёА-ЯЁ\-]{1,}\s+[А-ЯЁ][а-яёА-ЯЁ\-]{3,})'
        r'\s+\d{2}[./]\d{2}[./]\d{4}',
        text
    )
    if m:
        fio = m.group(1).strip()
        if not any(w in fio.lower() for w in _FIO_EXCLUDE) and len(fio.split()) >= 2:
            return fio

    # Стратегия 2: явные метки
    m = re.search(
        r'(?:Ф\.И\.О\.\s*заявителя|ФИО)[:\s]+'
        r'([А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)?)',
        text, re.IGNORECASE
    )
    if m:
        fio = m.group(1).strip()
        if not any(w in fio.lower() for w in _FIO_EXCLUDE):
            return fio

    # Стратегия 3: три слова с заглавной буквы
    candidates = []
    for m in re.finditer(r'([А-ЯЁ][а-яё]{2,}\s+[А-ЯЁ][а-яё]{2,}\s+[А-ЯЁ][а-яё]{4,})', text):
        fio = m.group(1).strip()
        if not any(w in fio.lower() for w in _FIO_EXCLUDE):
            candidates.append(fio)
    return candidates[0] if candidates else ""


def extract_routes_and_dates(text: str) -> Tuple[str, str, str, str]:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    table_start = next(
        (i for i, l in enumerate(lines) if re.search(r'маршрут.*перемещ', l, re.IGNORECASE)),
        -1
    )

    route_rows: List[Tuple[str, str, str]] = []

    if table_start >= 0:
        for line in lines[table_start + 1: table_start + 15]:
            cities = _find_cities_in_line(line)
            dates = _find_dates(line)
            if len(cities) >= 2 and dates:
                route_rows.append((cities[0], cities[1], dates[0]))
            elif len(cities) == 1 and dates:
                route_rows.append((cities[0], '', dates[0]))

    # Fallback: ищем пары город-город с датой
    if not route_rows:
        pattern = re.compile(
            r'([А-ЯЁ][а-яё\-]{2,}(?:\s+[А-ЯЁ][а-яё\-]+)?)'
            r'\s*[-–—]\s*'
            r'([А-ЯЁ][а-яё\-]{2,}(?:\s+[А-ЯЁ][а-яё\-]+)?)'
            r'.*?(\d{1,2}[./]\d{1,2}[./]\d{2,4})',
            re.DOTALL
        )
        for m in pattern.finditer(text):
            dm = DATE_RE.match(m.group(3))
            if dm:
                route_rows.append((m.group(1).strip(), m.group(2).strip(),
                                   _normalize_date(*dm.groups())))
            if len(route_rows) >= 2:
                break

    r1 = r2 = d1 = d2 = ""
    if route_rows:
        f, t, d = route_rows[0]
        r1 = f"{f} - {t}" if f and t else f or t
        d1 = d
    if len(route_rows) >= 2:
        f, t, d = route_rows[1]
        r2 = f"{f} - {t}" if f and t else f or t
        d2 = d
    return r1, r2, d1, d2


def extract_reason(text: str) -> str:
    text_lower = text.lower()
    scores: Dict[str, int] = {}
    for pattern, label in REASON_MAP:
        count = len(re.findall(pattern, text_lower))
        if count:
            scores[label] = count
    return max(scores, key=scores.__getitem__) if scores else ""


def extract_phone(text: str) -> str:
    m = PHONE_RE.search(text)
    return m.group(0) if m else ""


def extract_passport(text: str) -> Tuple[str, str]:
    # Российский: 4 цифры + 6 цифр
    m = re.search(r'\b(\d{4})\s+(\d{6})\b', text)
    if m:
        return m.group(1), m.group(2)
    # Иностранный: буквы + цифры
    m = re.search(r'\b([A-Z]{1,3})\s*(\d{6,9})\b', text)
    if m:
        return m.group(1), m.group(2)
    # Только номер
    m = re.search(r'\b(\d{7,9})\b', text)
    if m:
        return "", m.group(1)
    return "", ""


def extract_birth_date(text: str) -> str:
    for m in DATE_RE.finditer(text):
        day, month, year = m.groups()
        y = int(year) if len(year) == 4 else 2000 + int(year)
        if 1950 <= y <= 2010:
            return _normalize_date(day, month, year)
    return ""


def process_pdf_page(page_text: str, source_file: str) -> Optional[Dict]:
    if not page_text or len(page_text.strip()) < 30:
        return None
    if not re.search(r'заявк[аи].*билет|билет.*заявк', page_text, re.IGNORECASE):
        return None
    fio = extract_fio(page_text)
    if not fio:
        return None
    r1, r2, d1, d2 = extract_routes_and_dates(page_text)
    doc_series, doc_num = extract_passport(page_text)
    return {
        "source_file": source_file,
        "fio": fio,
        "birth_date": extract_birth_date(page_text),
        "doc_series": doc_series,
        "doc_num": doc_num,
        "route": r1,
        "date": d1,
        "route2": r2,
        "date2": d2,
        "reason": extract_reason(page_text),
        "phone": extract_phone(page_text),
    }


def process_pdf_file(pdf_path: str) -> List[Dict]:
    filename = os.path.basename(pdf_path)
    results = []
    try:
        doc = fitz.open(pdf_path)
        for i, page in enumerate(doc):
            text = _ocr_page(page)
            result = process_pdf_page(text, filename)
            if result:
                result["page_num"] = i + 1
                results.append(result)
                logger.info("Стр. %d: %s", i + 1, result["fio"])
        doc.close()
    except Exception as e:
        logger.error("Ошибка обработки PDF %s: %s", pdf_path, e)
    return results


def process_pdf_folder(folder_path: str, progress_callback=None) -> List[Dict]:
    pdf_files = list(Path(folder_path).glob("*.pdf"))
    all_results = []
    total = len(pdf_files)
    for idx, pdf_file in enumerate(pdf_files):
        if progress_callback:
            progress_callback(idx, total, f"Обработка: {pdf_file.name}")
        all_results.extend(process_pdf_file(str(pdf_file)))
    if progress_callback:
        progress_callback(total, total, "Готово!")
    return all_results
