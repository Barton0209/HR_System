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


def _deskew(img: np.ndarray) -> Tuple[np.ndarray, float]:
    """Коррекция перекоса через преобразование Хафа."""
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if len(img.shape) == 3 else img
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLines(edges, 1, np.pi / 180, threshold=100)
    if lines is not None and len(lines) > 3:
        angles = []
        for line in lines[:20]:
            rho, theta = line[0]
            angle = np.degrees(theta) - 90
            if -45 < angle < 45:
                angles.append(angle)
        if angles:
            median_angle = float(np.median(angles))
            if abs(median_angle) > 0.5:
                h, w = img.shape[:2]
                M = cv2.getRotationMatrix2D((w // 2, h // 2), median_angle, 1.0)
                img = cv2.warpAffine(img, M, (w, h),
                                     flags=cv2.INTER_CUBIC,
                                     borderMode=cv2.BORDER_REPLICATE)
                return img, median_angle
    return img, 0.0


def _remove_moire(img: np.ndarray) -> np.ndarray:
    """Подавление муара через FFT-фильтрацию."""
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if len(img.shape) == 3 else img
    dft = np.fft.fftshift(np.fft.fft2(gray))
    magnitude = np.log(np.abs(dft) + 1)
    h, w = magnitude.shape
    cy, cx = h // 2, w // 2
    y, x = np.ogrid[:h, :w]
    dist = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    lo, hi = int(min(h, w) * 0.05), int(min(h, w) * 0.15)
    moire_band = (dist > lo) & (dist < hi)
    if magnitude[moire_band].mean() > magnitude.mean() * 2.5:
        mask = np.ones_like(dft, dtype=np.float32)
        mask[moire_band] = 0.3
        result = np.real(np.fft.ifft2(np.fft.ifftshift(dft * mask))).astype(np.uint8)
        result = cv2.bilateralFilter(result, 5, 30, 30)
        return cv2.cvtColor(result, cv2.COLOR_GRAY2RGB) if len(img.shape) == 3 else result
    return img


def _sharpen_text(img: np.ndarray) -> np.ndarray:
    """Избирательное повышение резкости текстовых областей."""
    kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if len(img.shape) == 3 else img
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, text_mask = cv2.threshold(cv2.subtract(gray, blur), 15, 255, cv2.THRESH_BINARY)
    text_mask = cv2.dilate(text_mask, np.ones((2, 2), np.uint8)) / 255.0
    sharpened = cv2.filter2D(img, -1, kernel)
    if len(img.shape) == 3:
        m = cv2.cvtColor(text_mask.astype(np.float32), cv2.COLOR_GRAY2RGB) * 0.3
        return np.clip(img * (1 - m) + sharpened * m, 0, 255).astype(np.uint8)
    return np.clip(img * (1 - text_mask * 0.3) + sharpened * (text_mask * 0.3), 0, 255).astype(np.uint8)


def _preprocess(img_array: np.ndarray) -> np.ndarray:
    """Полный пайплайн предобработки: deskew → moire → CLAHE → sharpen → binarize."""
    img, _ = _deskew(img_array)
    img = _remove_moire(img)
    # CLAHE на L-канал (LAB)
    if len(img.shape) == 3:
        lab = cv2.cvtColor(img, cv2.COLOR_RGB2LAB)
        l, a, b = cv2.split(lab)
        l = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(l)
        img = cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2RGB)
    else:
        img = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(img)
    img = _sharpen_text(img)
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if len(img.shape) == 3 else img
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
                # MRZ-экстракция
                mrz = extract_mrz(text)
                if mrz:
                    result['mrz'] = mrz
                    if not result.get('doc_series') and mrz.get('doc_num'):
                        result['doc_num'] = mrz['doc_num']
                    if not result.get('birth_date') and mrz.get('dob'):
                        result['birth_date'] = mrz['dob']
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


# ---------------------------------------------------------------------------
# MRZ-экстрактор (паспорта 23 стран, ICAO TD3/TD1)
# ---------------------------------------------------------------------------

MRZ_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<")
_MRZ_REPLACEMENTS = {
    ' ': '<', '«': '<', '»': '<', '[': '<', ']': '<', '{': '<', '}': '<',
    'О': '0', 'В': '8', 'З': '3', 'Б': '6',
}

# Веса для контрольной цифры ICAO
_ICAO_WEIGHTS = [7, 3, 1]
_ICAO_MAP = {c: i for i, c in enumerate('0123456789')}
_ICAO_MAP.update({c: 10 + i for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ')})
_ICAO_MAP['<'] = 0


def _icao_check(data: str, digit: str) -> bool:
    """Проверка контрольной цифры ICAO."""
    try:
        total = sum(_ICAO_MAP.get(c, 0) * _ICAO_WEIGHTS[i % 3] for i, c in enumerate(data))
        return str(total % 10) == digit
    except Exception:
        return False


def _clean_mrz(text: str) -> str:
    result = []
    for c in text.upper():
        if c in MRZ_CHARS:
            result.append(c)
        elif c in _MRZ_REPLACEMENTS:
            result.append(_MRZ_REPLACEMENTS[c])
    return ''.join(result)


def _looks_like_mrz(text: str) -> bool:
    upper = sum(1 for c in text if c.isupper() or c.isdigit() or c == '<')
    return upper / max(len(text), 1) > 0.7 and len(text) > 15


def _parse_td3(line1: str, line2: str) -> Dict:
    """Парсинг TD3 MRZ (паспорт, 2×44)."""
    l1 = line1.ljust(44, '<')[:44]
    l2 = line2.ljust(44, '<')[:44]

    # Строка 1: тип, страна, ФИО
    doc_type = l1[0:2].strip('<')
    country = l1[2:5].strip('<')
    name_field = l1[5:44]
    parts = name_field.split('<<', 1)
    surname = parts[0].replace('<', ' ').strip()
    given = parts[1].replace('<', ' ').strip() if len(parts) > 1 else ''

    # Строка 2: номер, дата рождения, пол, срок, личный номер
    doc_num = l2[0:9].strip('<')
    check1 = l2[9]
    dob_raw = l2[13:19]
    check2 = l2[19]
    sex = l2[20]
    expiry_raw = l2[21:27]
    check3 = l2[27]

    def _fmt_date(d: str) -> str:
        if len(d) != 6:
            return ''
        yy, mm, dd = d[0:2], d[2:4], d[4:6]
        year = (2000 + int(yy)) if int(yy) <= 30 else (1900 + int(yy))
        return f"{dd}.{mm}.{year}"

    valid_num = _icao_check(l2[0:9], check1)
    valid_dob = _icao_check(dob_raw, check2)
    valid_exp = _icao_check(expiry_raw, check3)
    confidence = sum([valid_num, valid_dob, valid_exp]) / 3

    return {
        'mrz_type': 'TD3',
        'doc_type': doc_type,
        'country': country,
        'surname': surname,
        'given_names': given,
        'doc_num': doc_num,
        'dob': _fmt_date(dob_raw),
        'sex': sex if sex in ('M', 'F') else '',
        'expiry': _fmt_date(expiry_raw),
        'mrz_valid': confidence >= 0.67,
        'mrz_confidence': round(confidence, 2),
    }


def extract_mrz(text: str) -> Optional[Dict]:
    """
    Извлечение MRZ из текста страницы.
    Возвращает словарь с данными или None если MRZ не найден.
    """
    lines = [_clean_mrz(l.strip()) for l in text.splitlines() if l.strip()]
    mrz_lines = [l for l in lines if _looks_like_mrz(l) and len(l) >= 20]

    if len(mrz_lines) < 2:
        return None

    # Ищем пару строк длиной ~44 (TD3)
    for i in range(len(mrz_lines) - 1):
        l1, l2 = mrz_lines[i], mrz_lines[i + 1]
        if len(l1) >= 40 and len(l2) >= 40:
            result = _parse_td3(l1, l2)
            if result['mrz_confidence'] > 0:
                logger.info("MRZ найден: %s %s (уверенность %.0f%%)",
                            result['surname'], result['given_names'],
                            result['mrz_confidence'] * 100)
                return result

    return None


def process_image_file(image_path: str) -> List[Dict]:
    """
    Обработка одиночного изображения (JPEG/PNG) как страницы документа.
    Используется для сканов паспортов и других документов.
    """
    filename = os.path.basename(image_path)
    results = []
    try:
        from PIL import Image as PILImage
        pil_img = PILImage.open(image_path).convert('RGB')
        img_array = np.array(pil_img)
        binary = _preprocess(img_array)
        if not TESSERACT_AVAILABLE:
            logger.warning("Tesseract недоступен, OCR изображения невозможен")
            return results
        import pytesseract
        text = pytesseract.image_to_string(
            PILImage.fromarray(binary), lang='rus+eng', config='--psm 6 --oem 3')
        result = process_pdf_page(text, filename)
        if result:
            result['page_num'] = 1
            # Пробуем извлечь MRZ
            mrz = extract_mrz(text)
            if mrz:
                result['mrz'] = mrz
                if not result.get('doc_series') and mrz.get('doc_num'):
                    result['doc_num'] = mrz['doc_num']
                if not result.get('birth_date') and mrz.get('dob'):
                    result['birth_date'] = mrz['dob']
            results.append(result)
    except Exception as e:
        logger.error("Ошибка обработки изображения %s: %s", image_path, e)
    return results
