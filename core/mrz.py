"""
MRZ (Machine Readable Zone) parser — общий модуль для паспортов.
Поддерживает TD3 (паспорта) и TD1 (ID-карты).
"""

import re
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum


class MRZType(Enum):
    TD1 = "TD1"  # ID-карта: 3 строки × 30 символов
    TD3 = "TD3"  # Паспорт: 2 строки × 44 символа


@dataclass
class MRZData:
    """Структурированные данные MRZ."""
    mrz_type: str
    doc_type: str
    country: str
    surname: str
    given_names: str
    doc_num: str
    doc_num_check: bool
    nationality: str
    dob: str  # DD.MM.YYYY
    dob_check: bool
    sex: str  # M/F
    expiry: str  # DD.MM.YYYY
    expiry_check: bool
    optional_data: str
    composite_check: bool
    mrz_valid: bool
    confidence: float  # 0-1


# ICAO веса для контрольных цифр
_ICAO_WEIGHTS = [7, 3, 1]
_ICAO_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ<"
_ICAO_VALUES = {c: i for i, c in enumerate(_ICAO_CHARS)}

# Замены для OCR-ошибок
_MRZ_REPLACEMENTS = {
    '0': 'O',  # Ноль на букву O (редко)
    '8': 'B',  # Восемь на B
    '5': 'S',  # Пять на S
    '1': 'I',  # Один на I
    ' ': '<',  # Пробел на заполнитель
    '«': '<', '»': '<',
    '[': '<', ']': '<',
    '{': '<', '}': '<',
}


def _calculate_check_digit(data: str) -> int:
    """Вычисление контрольной цифры ICAO."""
    total = 0
    for i, char in enumerate(data):
        value = _ICAO_VALUES.get(char, 0)
        total += value * _ICAO_WEIGHTS[i % 3]
    return total % 10


def _verify_check_digit(data: str, check_digit: str) -> bool:
    """Проверка контрольной цифры."""
    try:
        expected = _calculate_check_digit(data)
        return str(expected) == check_digit
    except Exception:
        return False


def _clean_mrz_line(line: str) -> str:
    """Очистка строки MRZ от OCR-артефактов."""
    line = line.upper().strip()
    result = []
    for char in line:
        if char in _ICAO_CHARS:
            result.append(char)
        elif char in _MRZ_REPLACEMENTS:
            result.append(_MRZ_REPLACEMENTS[char])
    return ''.join(result)


def _looks_like_mrz(line: str) -> bool:
    """Проверка, похожа ли строка на MRZ."""
    if len(line) < 30:
        return False

    # MRZ содержит только заглавные буквы, цифры и <
    valid_chars = sum(1 for c in line if c in _ICAO_CHARS)
    return valid_chars / len(line) > 0.9


def _parse_date(mrz_date: str) -> Optional[str]:
    """Парсинг даты из формата YYMMDD в DD.MM.YYYY."""
    if len(mrz_date) != 6 or not mrz_date.isdigit():
        return None

    yy, mm, dd = mrz_date[0:2], mrz_date[2:4], mrz_date[4:6]

    # Определение века
    year = int(yy)
    if year <= 30:
        year += 2000
    else:
        year += 1900

    return f"{dd}.{mm}.{year}"


def _extract_name(name_field: str) -> Tuple[str, str]:
    """Извлечение фамилии и имен из поля MRZ."""
    # Заменяем < на пробел и разбиваем
    parts = name_field.replace('<', ' ').strip().split()

    if len(parts) >= 2:
        surname = parts[0]
        given_names = ' '.join(parts[1:])
    elif len(parts) == 1:
        surname = parts[0]
        given_names = ""
    else:
        surname = ""
        given_names = ""

    return surname, given_names


def parse_td3(line1: str, line2: str) -> Optional[MRZData]:
    """
    Парсинг TD3 MRZ (паспорт, 2 строки по 44 символа).
    """
    # Нормализация
    l1 = line1.ljust(44, '<')[:44]
    l2 = line2.ljust(44, '<')[:44]

    # Проверка длины
    if len(l1) < 44 or len(l2) < 44:
        return None

    # Строка 1
    doc_type = l1[0:2].strip('<')
    country = l1[2:5]
    name_field = l1[5:44]

    surname, given_names = _extract_name(name_field)

    # Строка 2
    doc_num = l2[0:9].strip('<')
    doc_num_check = l2[9] if len(l2) > 9 else '<'
    nationality = l2[10:13]
    dob_raw = l2[13:19]
    dob_check = l2[19] if len(l2) > 19 else '<'
    sex = l2[20] if len(l2) > 20 else '<'
    expiry_raw = l2[21:27]
    expiry_check = l2[27] if len(l2) > 27 else '<'
    optional_data = l2[28:42].strip('<')
    composite_check = l2[42] if len(l2) > 42 else '<'

    # Проверка контрольных цифр
    doc_num_valid = _verify_check_digit(doc_num, doc_num_check)
    dob_valid = _verify_check_digit(dob_raw, dob_check)
    expiry_valid = _verify_check_digit(expiry_raw, expiry_check)

    # Композитная проверка (строка 1 + строка 2 до контрольной цифры)
    composite_data = l1 + l2[0:10] + l2[13:20] + l2[21:43]
    composite_valid = _verify_check_digit(composite_data, composite_check)

    # Общая уверенность
    checks = [doc_num_valid, dob_valid, expiry_valid, composite_valid]
    confidence = sum(checks) / len(checks)

    return MRZData(
        mrz_type="TD3",
        doc_type=doc_type,
        country=country,
        surname=surname,
        given_names=given_names,
        doc_num=doc_num,
        doc_num_check=doc_num_valid,
        nationality=nationality,
        dob=_parse_date(dob_raw) or "",
        dob_check=dob_valid,
        sex=sex if sex in ('M', 'F') else '',
        expiry=_parse_date(expiry_raw) or "",
        expiry_check=expiry_valid,
        optional_data=optional_data,
        composite_check=composite_valid,
        mrz_valid=confidence >= 0.75,
        confidence=confidence,
    )


def parse_td1(line1: str, line2: str, line3: str) -> Optional[MRZData]:
    """
    Парсинг TD1 MRZ (ID-карта, 3 строки по 30 символов).
    """
    # Нормализация
    l1 = line1.ljust(30, '<')[:30]
    l2 = line2.ljust(30, '<')[:30]
    l3 = line3.ljust(30, '<')[:30]

    if len(l1) < 30 or len(l2) < 30 or len(l3) < 30:
        return None

    # TD1 структура отличается от TD3
    doc_type = l1[0:2].strip('<')
    country = l1[2:5]
    doc_num = l1[5:14].strip('<')
    doc_num_check = l1[14]
    optional_data_1 = l1[15:30].strip('<')

    dob_raw = l2[0:6]
    dob_check = l2[6]
    sex = l2[7] if len(l2) > 7 else '<'
    expiry_raw = l2[8:14]
    expiry_check = l2[14]
    nationality = l2[15:18]
    optional_data_2 = l2[18:29].strip('<')
    composite_check = l2[29] if len(l2) > 29 else '<'

    name_field = l3[0:30]
    surname, given_names = _extract_name(name_field)

    # Проверки
    doc_num_valid = _verify_check_digit(doc_num, doc_num_check)
    dob_valid = _verify_check_digit(dob_raw, dob_check)
    expiry_valid = _verify_check_digit(expiry_raw, expiry_check)

    composite_data = l1[5:30] + l2[0:7] + l2[8:15] + l2[18:29]
    composite_valid = _verify_check_digit(composite_data, composite_check)

    checks = [doc_num_valid, dob_valid, expiry_valid, composite_valid]
    confidence = sum(checks) / len(checks)

    return MRZData(
        mrz_type="TD1",
        doc_type=doc_type,
        country=country,
        surname=surname,
        given_names=given_names,
        doc_num=doc_num,
        doc_num_check=doc_num_valid,
        nationality=nationality,
        dob=_parse_date(dob_raw) or "",
        dob_check=dob_valid,
        sex=sex if sex in ('M', 'F') else '',
        expiry=_parse_date(expiry_raw) or "",
        expiry_check=expiry_valid,
        optional_data=optional_data_1 + optional_data_2,
        composite_check=composite_valid,
        mrz_valid=confidence >= 0.75,
        confidence=confidence,
    )


def extract_mrz_from_text(text: str) -> Optional[MRZData]:
    """
    Извлечение MRZ из произвольного текста.

    Args:
        text: Текст, возможно содержащий MRZ

    Returns:
        MRZData или None
    """
    lines = text.upper().split('\n')

    # Очистка и фильтрация
    mrz_lines = []
    for line in lines:
        cleaned = _clean_mrz_line(line)
        if _looks_like_mrz(cleaned):
            mrz_lines.append(cleaned)

    if len(mrz_lines) < 2:
        return None

    # Ищем TD3 (паспорт)
    for i in range(len(mrz_lines) - 1):
        l1, l2 = mrz_lines[i], mrz_lines[i + 1]
        if len(l1) >= 44 and len(l2) >= 44:
            result = parse_td3(l1, l2)
            if result and result.confidence > 0:
                return result

    # Ищем TD1 (ID-карта)
    for i in range(len(mrz_lines) - 2):
        l1, l2, l3 = mrz_lines[i], mrz_lines[i + 1], mrz_lines[i + 2]
        if len(l1) >= 30 and len(l2) >= 30 and len(l3) >= 30:
            result = parse_td1(l1, l2, l3)
            if result and result.confidence > 0:
                return result

    return None


def mrz_to_dict(mrz_data: MRZData) -> Dict:
    """Конвертация MRZData в словарь."""
    return {
        "mrz_type": mrz_data.mrz_type,
        "doc_type": mrz_data.doc_type,
        "country": mrz_data.country,
        "surname": mrz_data.surname,
        "given_names": mrz_data.given_names,
        "doc_num": mrz_data.doc_num,
        "nationality": mrz_data.nationality,
        "dob": mrz_data.dob,
        "sex": mrz_data.sex,
        "expiry": mrz_data.expiry,
        "optional_data": mrz_data.optional_data,
        "mrz_valid": mrz_data.mrz_valid,
        "confidence": mrz_data.confidence,
        "checks": {
            "doc_num": mrz_data.doc_num_check,
            "dob": mrz_data.dob_check,
            "expiry": mrz_data.expiry_check,
            "composite": mrz_data.composite_check,
        }
    }