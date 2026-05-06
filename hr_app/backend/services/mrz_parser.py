"""
MRZ Parser - Парсер MRZ по стандарту ICAO 9303 (TD3) для российских паспортов
Реализация на основе T3.md
"""
import re
from datetime import datetime
from typing import Optional, Dict, Any


class MRZParser:
    """Парсер MRZ по стандарту ICAO 9303 (TD3) для российских паспортов."""

    def __init__(self, line1: str, line2: str):
        self.line1 = line1
        self.line2 = line2
        self.raw_data: Dict[str, Any] = {}
        self.errors: list = []

    @staticmethod
    def clean_mrz_line(line: str) -> str:
        """Удаляет недопустимые символы, оставляет буквы, цифры, < и пробелы."""
        return re.sub(r'[^A-Z0-9<]', '', line.upper())

    def validate_line_length(self) -> bool:
        """Проверяет, что обе строки имеют длину 44 символа."""
        l1 = len(self.clean_mrz_line(self.line1))
        l2 = len(self.clean_mrz_line(self.line2))
        if l1 != 44 or l2 != 44:
            self.errors.append(f"Неверная длина строк: line1={l1}, line2={l2} (ожидается 44)")
            return False
        return True

    @staticmethod
    def compute_check_digit(data: str) -> int:
        """
        Вычисляет контрольную цифру для строки по алгоритму ICAO.
        Веса: 7, 3, 1, 7, 3, 1, ...
        """
        weights = [7, 3, 1]
        total = 0
        for i, ch in enumerate(data):
            if ch.isdigit():
                val = int(ch)
            elif ch.isalpha():
                val = ord(ch) - 55  # A=10, B=11, ..., Z=35
            else:
                val = 0  # '<' или другой символ
            total += val * weights[i % 3]
        return total % 10

    def parse(self) -> Dict[str, Any]:
        """Основной метод разбора. Возвращает словарь с данными."""
        if not self.validate_line_length():
            return {"error": self.errors}

        line1 = self.clean_mrz_line(self.line1)
        line2 = self.clean_mrz_line(self.line2)

        # ---------- Первая строка ----------
        doc_type = line1[0:2]  # 'P<'
        issuer = line1[2:5]  # 'RUS'
        # Остальное: фамилия и имя
        remainder = line1[5:]
        # Разделитель << между фамилией и именем
        if '<<' not in remainder:
            self.errors.append("Не найдено разделителя '<<' между фамилией и именем")
            return {"error": self.errors}

        parts = remainder.split('<<', 1)
        surname = parts[0].replace('<', ' ').strip()
        given_names = parts[1].replace('<', ' ').strip() if len(parts) > 1 else ''

        # ---------- Вторая строка ----------
        passport_number = line2[0:9].rstrip('<')
        check_digit_passport = line2[9]
        nationality = line2[10:13]
        birth_date_raw = line2[14:20]
        check_digit_birth = line2[20]
        sex = line2[21]
        expiry_date_raw = line2[22:28]
        check_digit_expiry = line2[28]
        personal_number = line2[29:43].rstrip('<')
        check_digit_personal = line2[42]
        final_check = line2[43]

        # Проверка контрольных цифр
        computed_cd_passport = self.compute_check_digit(line2[0:9])
        if str(computed_cd_passport) != check_digit_passport:
            self.errors.append(
                f"Контрольная цифра номера паспорта не совпадает: "
                f"ожидалось {computed_cd_passport}, получено {check_digit_passport}"
            )

        computed_cd_birth = self.compute_check_digit(birth_date_raw)
        if str(computed_cd_birth) != check_digit_birth:
            self.errors.append(
                f"Контрольная цифра даты рождения не совпадает: "
                f"ожидалось {computed_cd_birth}, получено {check_digit_birth}"
            )

        computed_cd_expiry = self.compute_check_digit(expiry_date_raw)
        if str(computed_cd_expiry) != check_digit_expiry:
            self.errors.append(
                f"Контрольная цифра срока действия не совпадает: "
                f"ожидалось {computed_cd_expiry}, получено {check_digit_expiry}"
            )

        if personal_number.strip():
            computed_cd_personal = self.compute_check_digit(personal_number)
            if str(computed_cd_personal) != check_digit_personal:
                self.errors.append(
                    f"Контрольная цифра личного номера не совпадает: "
                    f"ожидалось {computed_cd_personal}, получено {check_digit_personal}"
                )

        # Общая контрольная цифра
        composite_data = line2[0:10] + line2[11:20] + line2[21:29] + line2[29:43]
        computed_final = self.compute_check_digit(composite_data)
        if str(computed_final) != final_check:
            self.errors.append(
                f"Итоговая контрольная цифра не совпадает: "
                f"ожидалось {computed_final}, получено {final_check}"
            )

        # Преобразование дат
        try:
            birth_date = datetime.strptime(birth_date_raw, "%y%m%d")
        except ValueError:
            birth_date = None
            self.errors.append(f"Неверная дата рождения: {birth_date_raw}")

        try:
            expiry_date = datetime.strptime(expiry_date_raw, "%y%m%d")
        except ValueError:
            expiry_date = None
            self.errors.append(f"Неверная дата окончания срока действия: {expiry_date_raw}")

        # Пол
        sex_map = {'M': 'Мужской', 'F': 'Женский', '<': 'Не указан'}
        sex_readable = sex_map.get(sex, 'Неизвестно')

        result = {
            'document_type': doc_type,
            'issuer': issuer,
            'surname': surname,
            'given_names': given_names,
            'full_name': f"{surname} {given_names}".strip(),
            'passport_number': passport_number,
            'nationality': nationality,
            'birth_date': birth_date.strftime("%d.%m.%Y") if birth_date else None,
            'birth_date_raw': birth_date_raw,
            'sex': sex_readable,
            'sex_code': sex,
            'expiry_date': expiry_date.strftime("%d.%m.%Y") if expiry_date else None,
            'expiry_date_raw': expiry_date_raw,
            'personal_number': personal_number if personal_number.strip() else None,
            'mrz_line1': line1,
            'mrz_line2': line2,
            'check_digits_valid': len(self.errors) == 0,
            'errors': self.errors if self.errors else None
        }

        return result

    @classmethod
    def from_text(cls, text: str) -> Optional['MRZParser']:
        """Создание парсера из текста (две строки MRZ)."""
        lines = [line.strip() for line in text.strip().split('\n') if line.strip()]
        if len(lines) < 2:
            return None
        return cls(lines[0], lines[1])


def parse_mrz(text: str) -> Dict[str, Any]:
    """
    Удобная функция для парсинга MRZ из текста.
    
    Args:
        text: Текст содержащий две строки MRZ
        
    Returns:
        Словарь с распознанными данными или ошибкой
    """
    parser = MRZParser.from_text(text)
    if not parser:
        return {"error": ["Не удалось выделить две строки MRZ из текста"]}
    return parser.parse()
