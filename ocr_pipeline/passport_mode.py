# ocr_pipeline/passport_mode.py
"""
Режим 1: PASSPORT
=================
Каскадная обработка паспортов (РФ и иностранные).
Каждый метод дополняет только пустые поля — не перезаписывает уже найденное.

Порядок методов (по убыванию надёжности):
  M1. Имя файла/папки     — ФИО всегда известно
  M2. MRZ (ICAO TD3)      — ФИО лат., дата рождения, срок, номер, гражданство
  M3. PassportEye         — альтернативный MRZ-детектор (если M2 не нашёл)
  M4. Regex по OCR-тексту — серия/номер, дата выдачи, орган, код подр., адрес
  M5. Дата-fallback       — все даты из текста, распределяем по диапазонам
  M6. Транслитерация      — если ФИО есть, но латиница пустая
"""

import re
import logging
from datetime import datetime as _dt
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# ── Зависимости (опциональные) ────────────────────────────────────────────────

# PassportEye
_PASSPORT_EYE_OK = False
try:
    from passporteye import read_mrz
    _PASSPORT_EYE_OK = True
except ImportError:
    pass

# mrz (библиотека mrz-checker)
_MRZ_LIB_OK = False
try:
    from mrz.checker.td3 import TD3CodeChecker
    _MRZ_LIB_OK = True
except ImportError:
    pass

# iuliia — транслитерация по ГОСТ
_IULIIA_OK = False
try:
    import iuliia
    _IULIIA_OK = True
except ImportError:
    pass

# ── Транслитерация ────────────────────────────────────────────────────────────

_TRANSLIT = {
    'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'E',
    'Ж': 'ZH', 'З': 'Z', 'И': 'I', 'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M',
    'Н': 'N', 'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U',
    'Ф': 'F', 'Х': 'KH', 'Ц': 'TS', 'Ч': 'CH', 'Ш': 'SH', 'Щ': 'SHCH',
    'Ы': 'Y', 'Э': 'E', 'Ю': 'YU', 'Я': 'YA', 'Ь': '', 'Ъ': '',
}


def transliterate(name: str) -> str:
    if not name:
        return ""
    if _IULIIA_OK:
        try:
            return iuliia.translate(name, schema=iuliia.Schemas.GOST_52535_2006).upper()
        except Exception:
            pass
    return ''.join(_TRANSLIT.get(c, c) for c in name.upper())


# ── Вспомогательные функции ───────────────────────────────────────────────────

def _fill(result: dict, key: str, value: str):
    """Заполняет поле только если оно пустое."""
    if value and not result.get(key):
        result[key] = str(value).strip()


COUNTRIES = {
    'UZB': 'УЗБЕКИСТАН', 'UZBEKISTAN': 'УЗБЕКИСТАН', 'УЗБЕКИСТАН': 'УЗБЕКИСТАН',
    'KGZ': 'КИРГИЗИЯ',   'KYRGYZSTAN': 'КИРГИЗИЯ',   'КЫРГЫЗСТАН': 'КИРГИЗИЯ',
    'TJK': 'ТАДЖИКИСТАН','TAJIKISTAN': 'ТАДЖИКИСТАН', 'ТАДЖИКИСТАН': 'ТАДЖИКИСТАН',
    'KAZ': 'КАЗАХСТАН',  'KAZAKHSTAN': 'КАЗАХСТАН',
    'BLR': 'БЕЛАРУСЬ',   'BELARUS': 'БЕЛАРУСЬ',
    'ARM': 'АРМЕНИЯ',    'ARMENIA': 'АРМЕНИЯ',
    'AZE': 'АЗЕРБАЙДЖАН','AZERBAIJAN': 'АЗЕРБАЙДЖАН',
    'GEO': 'ГРУЗИЯ',     'GEORGIA': 'ГРУЗИЯ',
    'MDA': 'МОЛДОВА',    'MOLDOVA': 'МОЛДОВА',
    'UKR': 'УКРАИНА',    'UKRAINE': 'УКРАИНА',
    'SRB': 'СЕРБИЯ',     'SERBIA': 'СЕРБИЯ',
    'RUS': 'РОССИЯ',     'РОССИЯ': 'РОССИЯ',
}

DATE_RE = re.compile(r'(\d{1,2})[./\s](\d{1,2})[./\s](\d{4})')
SERIES_NUM_RU_RE = re.compile(r'\b(\d{2}[\s\-]?\d{2})[\s]+(\d{6})\b')
DEPT_CODE_RE = re.compile(r'\b(\d{3})[\-\s](\d{3})\b')
PASSPORT_FOREIGN_RE = re.compile(r'\b([A-Z]{1,3})\s*(\d{6,9})\b')


def _norm_date(d: str, m: str, y: str) -> str:
    return f"{d.zfill(2)}.{m.zfill(2)}.{y}"


def _find_dates(text: str) -> list:
    return [_norm_date(*g) for g in DATE_RE.findall(text)]


# ── M2: MRZ парсер (встроенный, без зависимостей) ────────────────────────────

_CYR_TO_LAT = {
    'А': 'A', 'В': 'B', 'Е': 'E', 'З': '3', 'И': 'I', 'К': 'K', 'М': 'M',
    'Н': 'H', 'О': 'O', 'Р': 'R', 'С': 'C', 'Т': 'T', 'У': 'Y', 'Х': 'X',
    'а': 'a', 'в': 'b', 'е': 'e', 'з': '3', 'и': 'i', 'к': 'k', 'м': 'm',
    'н': 'h', 'о': 'o', 'р': 'r', 'с': 'c', 'т': 't', 'у': 'y', 'х': 'x',
    'Ч': '4', 'Ш': 'W', 'Щ': 'W', 'Г': 'G', 'Д': 'D', 'Ж': 'J', 'Л': 'L',
    'П': 'P', 'Ф': 'F', 'Ц': 'C', 'Б': '6', 'Й': 'I', 'Ы': 'Y', 'Э': 'E',
    'Ё': 'E', 'Ю': 'U', 'Я': 'A', 'Ь': '', 'Ъ': '',
}

MRZ_LINE_RE = re.compile(r'([A-Z0-9<]{44})\s*\n?\s*([A-Z0-9<]{44})')
_MRZ_LINE2_RE = re.compile(r'^[A-Z0-9]{9}\d[A-Z]{3}[A-Z0-9]{6}\d[MF<]')


def _fix_mrz_ocr(line: str) -> str:
    return ''.join(_CYR_TO_LAT.get(ch, ch) for ch in line)


def _clean_mrz(line: str) -> str:
    return re.sub(r'[^A-Z0-9<]', '', line.upper())


def _mrz_check_digit(data: str) -> int:
    weights = [7, 3, 1]
    total = 0
    for i, ch in enumerate(data):
        if ch.isdigit():
            val = int(ch)
        elif ch.isalpha():
            val = ord(ch.upper()) - 55
        else:
            val = 0
        total += val * weights[i % 3]
    return total % 10


def _mrz_date(raw: str) -> str:
    try:
        return _dt.strptime(raw, '%y%m%d').strftime('%d.%m.%Y')
    except ValueError:
        return ""


def _parse_mrz_lines(line1: str, line2: str) -> dict:
    """Парсит пару MRZ строк TD3."""
    l1 = _clean_mrz(line1).ljust(44, '<')[:44]
    l2 = _clean_mrz(line2).ljust(44, '<')[:44]

    result = {"mrz_ok": False, "mrz_errors": []}

    name_field = l1[5:]
    if '<<' in name_field:
        surname_raw, given_raw = name_field.split('<<', 1)
        surname = surname_raw.replace('<', ' ').strip()
        given_parts = [p for p in given_raw.replace('<', ' ').split() if p]
        first_name  = given_parts[0] if given_parts else ''
        middle_name = given_parts[1] if len(given_parts) > 1 else ''
        result["fio_lat"] = f"{surname} {first_name} {middle_name}".strip()
    else:
        result["mrz_errors"].append("Нет разделителя '<<' в строке 1")

    passport_num = l2[0:9]
    nationality  = l2[10:13]
    birth_raw    = l2[13:19]
    birth_check  = l2[19]
    sex          = l2[20] if l2[20] in ('M', 'F') else ''
    expiry_raw   = l2[21:27]
    expiry_check = l2[27]
    total_check  = l2[43]

    checks = [
        (passport_num, l2[9],  "номера паспорта"),
        (birth_raw,    birth_check, "даты рождения"),
        (expiry_raw,   expiry_check, "срока действия"),
        (l2[0:43],     total_check, "общая"),
    ]
    all_ok = True
    for data, check, label in checks:
        if check.isdigit() and int(check) != _mrz_check_digit(data):
            result["mrz_errors"].append(f"Контрольная цифра {label} не совпадает")
            all_ok = False

    result["mrz_ok"]       = all_ok
    result["passport_num"] = passport_num.replace('<', '')
    result["nationality"]  = nationality
    result["birth_date"]   = _mrz_date(birth_raw)
    result["sex"]          = sex
    result["expiry_date"]  = _mrz_date(expiry_raw)
    return result


def _extract_mrz_builtin(text: str) -> dict:
    """Встроенный MRZ-детектор: ищет пару строк с << и паттерном строки 2."""
    lines = text.splitlines()
    candidates = []
    for line in lines:
        fixed   = _fix_mrz_ocr(line)
        cleaned = _clean_mrz(fixed)
        if len(cleaned) < 20:
            continue
        has_lt = '<<' in cleaned
        is_l2  = bool(_MRZ_LINE2_RE.match(cleaned))
        if len(cleaned) >= 25 or has_lt or is_l2:
            candidates.append((cleaned, has_lt, is_l2))

    # Ищем пару: строка с << + следующая строка 2
    for i in range(len(candidates) - 1):
        c1, has_lt1, _ = candidates[i]
        c2, _, is_l2   = candidates[i + 1]
        if has_lt1 and is_l2:
            return _parse_mrz_lines(c1.ljust(44, '<')[:44],
                                    c2.ljust(44, '<')[:44])

    # Fallback: строка с P + следующая с цифрами
    for i in range(len(candidates) - 1):
        c1, _, _ = candidates[i]
        c2, _, _ = candidates[i + 1]
        if c1.startswith('P') and re.match(r'[A-Z0-9]{7,}\d', c2):
            return _parse_mrz_lines(c1.ljust(44, '<')[:44],
                                    c2.ljust(44, '<')[:44])

    # Fallback: regex по всему тексту
    text_clean = re.sub(r'[^A-Z0-9<\n]', '', _fix_mrz_ocr(text).upper())
    m = MRZ_LINE_RE.search(text_clean)
    if m:
        return _parse_mrz_lines(m.group(1), m.group(2))

    return {}


# ── M3: PassportEye MRZ-детектор ─────────────────────────────────────────────

def _extract_mrz_passporteye(image_path: str) -> dict:
    """
    Использует PassportEye для детекции MRZ прямо на изображении.
    Более устойчив к перекосам и плохому качеству скана.
    """
    if not _PASSPORT_EYE_OK:
        return {}
    try:
        mrz = read_mrz(image_path)
        if mrz is None:
            return {}
        data = mrz.to_dict()
        # Нормализуем в наш формат
        result = {}
        names = []
        if data.get('surname'):
            names.append(data['surname'])
        if data.get('names'):
            names.append(data['names'])
        if names:
            result['fio_lat'] = ' '.join(names).strip()

        for src, dst in [('date_of_birth', 'birth_date'),
                         ('expiration_date', 'expiry_date'),
                         ('number', 'passport_num'),
                         ('nationality', 'nationality')]:
            if data.get(src):
                result[dst] = str(data[src])

        # Конвертируем даты из YYMMDD если нужно
        for key in ('birth_date', 'expiry_date'):
            val = result.get(key, '')
            if val and len(val) == 6 and val.isdigit():
                result[key] = _mrz_date(val)

        result['mrz_ok'] = data.get('valid_score', 0) > 50
        return result
    except Exception as e:
        logger.debug("PassportEye error: %s", e)
        return {}


# ── M2+M3: объединённый MRZ ───────────────────────────────────────────────────

def extract_mrz(text: str, image_path: Optional[str] = None) -> dict:
    """
    Пробует M2 (встроенный) → M3 (PassportEye).
    Возвращает лучший результат.
    """
    # M2: встроенный парсер
    result = _extract_mrz_builtin(text)
    if result.get('mrz_ok'):
        result['_source'] = 'builtin_mrz'
        return result

    # M3: PassportEye (если есть путь к файлу)
    if image_path:
        pe_result = _extract_mrz_passporteye(image_path)
        if pe_result:
            # Объединяем: PassportEye дополняет встроенный
            for k, v in pe_result.items():
                _fill(result, k, v)
            result['_source'] = 'passporteye'
            return result

    if result:
        result['_source'] = 'builtin_mrz_partial'
    return result


# ── Главные парсеры ───────────────────────────────────────────────────────────

def parse_passport_ru(text: str, fio_from_filename: str = "",
                      image_path: Optional[str] = None) -> dict:
    """
    Каскадный парсер российского паспорта.

    M1 → M2/M3 → M4 → M5 → M6
    Каждый метод заполняет только пустые поля.
    """
    result = {
        "fio": "", "fio_lat": "", "birth_date": "",
        "citizenship": "РОССИЯ", "doc_series_num": "", "issuer": "",
        "issue_date": "", "expiry_date": "", "dept_code": "", "address": "",
        "_methods": [],
    }
    text_upper = text.upper()

    # ── M1: имя файла ─────────────────────────────────────────────────
    _fill(result, "fio", fio_from_filename)
    if fio_from_filename:
        result["_methods"].append("M1:filename")

    # ── M2+M3: MRZ ────────────────────────────────────────────────────
    mrz = extract_mrz(text, image_path)
    if mrz:
        _fill(result, "fio_lat",      mrz.get("fio_lat", ""))
        _fill(result, "birth_date",   mrz.get("birth_date", ""))
        _fill(result, "expiry_date",  mrz.get("expiry_date", ""))
        mrz_num = mrz.get("passport_num", "")
        if mrz_num and len(mrz_num) >= 9:
            result["_mrz_num"] = mrz_num
        result["_methods"].append(mrz.get("_source", "M2:mrz"))

    # ── M4a: серия и номер — regex ────────────────────────────────────
    m = SERIES_NUM_RU_RE.search(text)
    if m:
        series = m.group(1).replace(' ', '').replace('-', '')
        _fill(result, "doc_series_num", f"{series[:2]} {series[2:]} {m.group(2)}")
        result["_methods"].append("M4a:series_regex")
    if not result["doc_series_num"]:
        alt = re.search(r'\b(\d{2})\s+(\d{2})\s+(\d{6})\b', text)
        if alt:
            _fill(result, "doc_series_num",
                  f"{alt.group(1)} {alt.group(2)} {alt.group(3)}")
    if not result["doc_series_num"] and result.get("_mrz_num"):
        n = result["_mrz_num"]
        _fill(result, "doc_series_num", f"{n[:2]} {n[2:4]} {n[4:]}")
        result["_methods"].append("M4a:series_from_mrz")
    result.pop("_mrz_num", None)

    # ── M4b: код подразделения ────────────────────────────────────────
    codes = DEPT_CODE_RE.findall(text)
    if codes:
        _fill(result, "dept_code", f"{codes[0][0]}-{codes[0][1]}")
        result["_methods"].append("M4b:dept_code")

    # ── M4c: орган выдачи ─────────────────────────────────────────────
    for pat in [
        r'(?:ОТДЕЛОМ|ОТДЕЛЕНИЕМ|УМВД|УФМС|ОМВД|МВД|ОВД|ОТДЕЛ)[^\n]{5,120}',
        r'(?:ВЫДАН|ISSUED BY)[:\s]+([^\n]{5,120})',
    ]:
        m = re.search(pat, text_upper)
        if m:
            _fill(result, "issuer", m.group(0).strip()[:120])
            result["_methods"].append("M4c:issuer_regex")
            break

    # ── M4d: адрес — блок после ЗАРЕГИСТРИРОВАН ───────────────────────
    addr_m = re.search(
        r'ЗАРЕГИСТРИРОВАН[А]?[\s\S]{0,20}?\n([\s\S]{10,300}?)'
        r'(?:РЕГИСТРАЦИОННОГО|ОТДЕЛ|$)',
        text_upper
    )
    if addr_m:
        addr_raw = addr_m.group(1).replace('\n', ' ').strip()
        _fill(result, "address", re.sub(r'\s{2,}', ' ', addr_raw)[:200])
        result["_methods"].append("M4d:address_block")
    else:
        m = re.search(r'(?:УЛ\.|УЛИЦА|ПР\.|ПРОСПЕКТ)[^\n]{5,120}', text_upper)
        if m:
            _fill(result, "address", m.group(0).strip()[:150])
            result["_methods"].append("M4d:address_street")

    # ── M5: дата-fallback ─────────────────────────────────────────────
    dates = _find_dates(text)
    birth_dates = [d for d in dates if 1940 <= int(d.split('.')[-1]) <= 2010]
    issue_dates = [d for d in dates if 2000 <= int(d.split('.')[-1]) <= 2030
                   and d not in birth_dates]
    if _fill(result, "birth_date", birth_dates[0] if birth_dates else ""):
        result["_methods"].append("M5:birth_date_fallback")
    if _fill(result, "issue_date", issue_dates[0] if issue_dates else ""):
        result["_methods"].append("M5:issue_date_fallback")

    # ── M6: транслитерация ────────────────────────────────────────────
    # Используем транслитерацию если fio_lat пустой ИЛИ содержит цифры/мусор из MRZ
    fio_lat = result.get("fio_lat", "")
    if result["fio"] and (not fio_lat or any(c.isdigit() for c in fio_lat)):
        result["fio_lat"] = transliterate(result["fio"])
        result["_methods"].append("M6:transliterate")

    return result


def parse_passport_foreign(text: str, fio_from_filename: str = "",
                            image_path: Optional[str] = None) -> dict:
    """
    Каскадный парсер иностранного паспорта.

    M1 → M2/M3 → M4 → M5 → M6
    """
    result = {
        "fio": "", "fio_lat": "", "birth_date": "",
        "citizenship": "", "doc_series_num": "", "issuer": "",
        "issue_date": "", "expiry_date": "", "dept_code": "", "address": "",
        "_methods": [],
    }
    text_upper = text.upper()

    # ── M1: имя файла ─────────────────────────────────────────────────
    _fill(result, "fio", fio_from_filename)
    if fio_from_filename:
        result["_methods"].append("M1:filename")

    # ── M2+M3: MRZ ────────────────────────────────────────────────────
    mrz = extract_mrz(text, image_path)
    if mrz:
        _fill(result, "fio_lat",       mrz.get("fio_lat", ""))
        _fill(result, "birth_date",    mrz.get("birth_date", ""))
        _fill(result, "expiry_date",   mrz.get("expiry_date", ""))
        _fill(result, "doc_series_num", mrz.get("passport_num", ""))
        nat = mrz.get("nationality", "")
        _fill(result, "citizenship",   COUNTRIES.get(nat, nat))
        result["_methods"].append(mrz.get("_source", "M2:mrz"))

    # ── M4a: серия/номер — regex ──────────────────────────────────────
    if not result["doc_series_num"]:
        m = PASSPORT_FOREIGN_RE.search(text_upper)
        if m:
            _fill(result, "doc_series_num", f"{m.group(1)} {m.group(2)}")
            result["_methods"].append("M4a:foreign_num_regex")

    # ── M4b: гражданство по ключевым словам ──────────────────────────
    if not result["citizenship"]:
        for key, country in COUNTRIES.items():
            if key in text_upper:
                result["citizenship"] = country
                result["_methods"].append("M4b:citizenship_keyword")
                break

    # ── M4c: орган выдачи ─────────────────────────────────────────────
    for pat in [
        r'(?:ISSUED BY|ВЫДАН)[:\s]+([^\n]{5,120})',
        r'(?:AUTHORITY|ОРГАН)[:\s]+([^\n]{5,120})',
    ]:
        m = re.search(pat, text_upper)
        if m:
            _fill(result, "issuer", m.group(0).strip()[:120])
            result["_methods"].append("M4c:issuer_regex")
            break

    # ── M5: дата-fallback ─────────────────────────────────────────────
    dates = _find_dates(text)
    birth_dates  = [d for d in dates if 1940 <= int(d.split('.')[-1]) <= 2010]
    future_dates = [d for d in dates if int(d.split('.')[-1]) > 2024]
    past_dates   = [d for d in dates if 2000 <= int(d.split('.')[-1]) <= 2024
                    and d not in birth_dates]
    if _fill(result, "birth_date",  birth_dates[0]  if birth_dates  else ""):
        result["_methods"].append("M5:birth_date_fallback")
    if _fill(result, "expiry_date", future_dates[0] if future_dates else ""):
        result["_methods"].append("M5:expiry_fallback")
    if _fill(result, "issue_date",  past_dates[0]   if past_dates   else ""):
        result["_methods"].append("M5:issue_date_fallback")

    # ── M6: транслитерация ────────────────────────────────────────────
    fio_lat = result.get("fio_lat", "")
    if result["fio"] and (not fio_lat or any(c.isdigit() for c in fio_lat)):
        result["fio_lat"] = transliterate(result["fio"])
        result["_methods"].append("M6:transliterate")

    # ── Нормализация гражданства — убираем OCR-мусор ─────────────────
    cit = result.get("citizenship", "")
    if cit and cit not in COUNTRIES.values():
        # Пробуем исправить через _fix_mrz_ocr (цифры → буквы обратно не работает,
        # поэтому ищем по расстоянию: считаем совпадающие символы)
        best_key, best_score = None, 0
        for key in COUNTRIES:
            if len(key) != 3:
                continue
            score = sum(a == b for a, b in zip(cit[:3], key))
            if score > best_score:
                best_score, best_key = score, key
        if best_key and best_score >= 1:
            result["citizenship"] = COUNTRIES[best_key]

    return result
