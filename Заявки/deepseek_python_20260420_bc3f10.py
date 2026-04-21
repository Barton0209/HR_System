import re
import json
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path

import pdfplumber


@dataclass
class Passport:
    series: str
    number: str


@dataclass
class Route:
    direction: str  # "туда" или "обратно"
    from_city: str
    to_city: str
    date: str
    transport: str


@dataclass
class Applicant:
    full_name: str
    birth_date: str
    position: str
    passport: Passport


@dataclass
class HrData:
    start_date: Optional[str]  # дата начала вахты
    months_worked: Optional[int]  # отработано месяцев
    is_shift_completed: bool  # вахта отработана?
    reason: str  # обоснование (межвахта, увольнение, командировка и т.д.)


@dataclass
class Contacts:
    phone: str
    email: str


@dataclass
class TicketRequest:
    applicant: Applicant
    routes: List[Route]
    justification: str  # тип поездки (межвахта, увольнение и т.д.)
    hr_data: HrData
    contacts: Contacts


# Паттерны для регулярных выражений
PATTERNS = {
    'fio': r'([А-ЯЁ][а-яё]+)\s+([А-ЯЁ][а-яё]+)\s+([А-ЯЁ][а-яё]+)',
    'date': r'(\d{2})\.(\d{2})\.(\d{4})',
    'date_ru': r'(\d{2})\.(\d{2})\.(\d{4})',
    'city': r'(Санкт-Петербург|Москва|Шымкент|Астана|Наманган|Самарканд|Алматы|Ташкент|О тел)',
    'reason_keywords': r'(межвахта|увольнение|командировка|междувахтовый отдых|трудоустройство|перевод|болезнь)',
    'passport': r'(?:ID|N)?\s*(\d{2,3})?\s*(\d{7,9})',  # серия и номер
    'phone': r'\+?7\s*\(?\d{3}\)?\s*\d{3}[-\s]?\d{2}[-\s]?\d{2}',
    'email': r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
    'months': r'(\d+)\s*мес',
    'start_date': r'дата начала вахты\s*(\d{2}\.\d{2}\.\d{4})',
    'transport': r'(АВИА|жд|поезд|автобус)'
}


def normalize_city(city: str) -> str:
    """Нормализация названий городов (исправление очевидных опечаток)"""
    corrections = {
        'О тел': 'Отел',  # возможно опечатка
        'Астана': 'Астана',
        'Шымкент': 'Шымкент',
        'Наманган': 'Наманган'
    }
    return corrections.get(city, city)


def extract_applicant(block_text: str) -> Optional[Applicant]:
    """Извлечение данных заявителя из текстового блока"""
    lines = block_text.split('\n')
    full_name = None
    birth_date = None
    position = None
    passport_series = ''
    passport_number = ''

    # Ищем строку с "Ф.И.О. заявителя"
    for i, line in enumerate(lines):
        if 'Ф.И.О. заявителя' in line:
            # часто ФИО находится справа или на следующей строке
            if i + 1 < len(lines):
                potential_name = lines[i + 1].strip()
                if re.match(PATTERNS['fio'], potential_name):
                    full_name = potential_name
                else:
                    # иногда имя в той же строке после двоеточия
                    parts = re.split(r'[:\t]+', line)
                    if len(parts) > 1:
                        potential_name = parts[1].strip()
                        if re.match(PATTERNS['fio'], potential_name):
                            full_name = potential_name
            break

    # Поиск даты рождения
    date_match = re.search(PATTERNS['date'], block_text)
    if date_match:
        birth_date = date_match.group(0)

    # Поиск должности (ищем "Должность заявителя" или "Монтажник" и т.д.)
    for line in lines:
        if 'Должность заявителя' in line:
            parts = re.split(r'[:\t]+', line)
            if len(parts) > 1:
                position = parts[1].strip()
            else:
                if line.find('Должность заявителя') != -1:
                    idx = line.find('Должность заявителя') + len('Должность заявителя')
                    position = line[idx:].strip()
            break
    if not position:
        # альтернативный поиск: после строки с "должность" или из списка профессий
        for line in lines:
            if any(prof in line for prof in ['Монтажник', 'Изолировщик', 'Слесарь']):
                position = line.strip()
                break

    # Поиск паспорта: ищем "Серия и номер документа" или ID/N
    for line in lines:
        if 'Серия и номер документа' in line or 'ID' in line or 'N' in line:
            # извлекаем цифры
            numbers = re.findall(r'\d{7,9}', line)
            if numbers:
                passport_number = numbers[0]
                # серия может быть перед номером (2-3 цифры)
                series_match = re.search(r'(\d{2,3})\s*' + passport_number, line)
                if series_match:
                    passport_series = series_match.group(1)
                else:
                    passport_series = ''
            else:
                # если номер не найден, ищем отдельно
                pass
            break

    if full_name and birth_date and position and passport_number:
        return Applicant(
            full_name=full_name,
            birth_date=birth_date,
            position=position,
            passport=Passport(series=passport_series, number=passport_number)
        )
    return None


def extract_routes(block_text: str) -> List[Route]:
    """Извлечение маршрутов из блока"""
    routes = []
    # Ищем таблицу маршрутов: строки с "Пункт отправления" и далее данные
    lines = block_text.split('\n')
    table_start = -1
    for i, line in enumerate(lines):
        if 'Маршрут(-ы) перемещения' in line:
            table_start = i
            break
    if table_start == -1:
        return routes

    # Перебираем строки после заголовка
    for i in range(table_start + 1, min(table_start + 10, len(lines))):
        line = lines[i].strip()
        # Пропускаем пустые
        if not line:
            continue
        # Проверяем, есть ли в строке признаки маршрута: город-город или дата
        # Ищем два города и дату
        cities = re.findall(PATTERNS['city'], line, re.IGNORECASE)
        dates = re.findall(PATTERNS['date'], line)
        transport = re.search(PATTERNS['transport'], line, re.IGNORECASE)
        if len(cities) >= 2 and dates:
            from_city = normalize_city(cities[0])
            to_city = normalize_city(cities[1])
            date = dates[0]
            trans = transport.group(0).upper() if transport else 'АВИА'
            # Определяем направление: первый маршрут - "туда", второй - "обратно"
            direction = 'туда' if len(routes) == 0 else 'обратно'
            routes.append(Route(
                direction=direction,
                from_city=from_city,
                to_city=to_city,
                date=date,
                transport=trans
            ))
            if len(routes) == 2:
                break
    return routes


def extract_justification_and_hr(block_text: str) -> tuple[str, HrData]:
    """Извлечение обоснования и кадровых данных"""
    reason = ''
    start_date = None
    months_worked = None
    is_shift_completed = False

    # Поиск обоснования в блоке кадров
    reason_match = re.search(PATTERNS['reason_keywords'], block_text, re.IGNORECASE)
    if reason_match:
        reason = reason_match.group(0).lower()
        # Подчёркивание или выделение может быть представлено повторением слова (например, "Увольнение")
        # Уточним: ищем слово, которое подчёркнуто или повторено в контексте
        # В тексте встречается "Увольнение" как подчёркнутое
    else:
        # По умолчанию "межвахта"
        reason = 'межвахта'

    # Поиск даты начала вахты
    start_match = re.search(PATTERNS['start_date'], block_text, re.IGNORECASE)
    if start_match:
        start_date = start_match.group(1)

    # Поиск отработанных месяцев
    months_match = re.search(PATTERNS['months'], block_text)
    if months_match:
        months_worked = int(months_match.group(1))

    # Проверка, отработана ли вахта (ищем "Да" рядом с "Фактически отработано")
    if 'Фактически отработано' in block_text:
        # Находим строку и смотрим, есть ли "Да" или "Нет"
        lines = block_text.split('\n')
        for i, line in enumerate(lines):
            if 'Фактически отработано' in line:
                # проверим текущую строку и следующую
                if 'Да' in line or (i + 1 < len(lines) and 'Да' in lines[i + 1]):
                    is_shift_completed = True
                else:
                    is_shift_completed = False
                break

    hr = HrData(
        start_date=start_date,
        months_worked=months_worked,
        is_shift_completed=is_shift_completed,
        reason=reason
    )
    return reason, hr


def extract_contacts(block_text: str) -> Contacts:
    """Извлечение контактов (телефон, email)"""
    phone = ''
    email = ''
    phone_match = re.search(PATTERNS['phone'], block_text)
    if phone_match:
        phone = phone_match.group(0)
    email_match = re.search(PATTERNS['email'], block_text, re.IGNORECASE)
    if email_match:
        email = email_match.group(0)
    return Contacts(phone=phone, email=email)


def split_into_applications(pdf_path: str) -> List[str]:
    """Разделение PDF на отдельные заявки по ключевому слову"""
    applications = []
    current_app = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            lines = text.split('\n')
            for line in lines:
                if 'Заявка на приобретение билетов' in line and current_app:
                    # Сохраняем предыдущую заявку
                    applications.append('\n'.join(current_app))
                    current_app = []
                current_app.append(line)
            # После обработки страницы не закрываем заявку, т.к. она может продолжаться
        if current_app:
            applications.append('\n'.join(current_app))
    return applications


def parse_application(app_text: str) -> Optional[TicketRequest]:
    """Парсинг одной заявки"""
    applicant = extract_applicant(app_text)
    if not applicant:
        return None
    routes = extract_routes(app_text)
    if not routes:
        # Если маршруты не найдены, пробуем альтернативный поиск по ключевым словам
        # Можно добавить fallback
        pass
    justification, hr_data = extract_justification_and_hr(app_text)
    contacts = extract_contacts(app_text)
    return TicketRequest(
        applicant=applicant,
        routes=routes,
        justification=justification,
        hr_data=hr_data,
        contacts=contacts
    )


def convert_to_dict(request: TicketRequest) -> Dict[str, Any]:
    """Преобразование объекта в JSON-совместимый словарь"""
    return {
        "заявитель": {
            "фио": request.applicant.full_name,
            "дата_рождения": request.applicant.birth_date,
            "должность": request.applicant.position,
            "паспорт": {
                "серия": request.applicant.passport.series,
                "номер": request.applicant.passport.number
            }
        },
        "маршруты": [
            {
                "направление": r.direction,
                "откуда": r.from_city,
                "куда": r.to_city,
                "дата_вылета": r.date,
                "транспорт": r.transport
            }
            for r in request.routes
        ],
        "обоснование": request.justification,
        "кадровые_данные": {
            "дата_начала_вахты": request.hr_data.start_date,
            "отработано_месяцев": request.hr_data.months_worked,
            "вахта_отработана": request.hr_data.is_shift_completed
        },
        "контакты": {
            "телефон": request.contacts.phone,
            "email": request.contacts.email
        }
    }


def main(pdf_path: str, output_json: str = "ticket_requests.json"):
    """Основная функция"""
    print(f"Обработка PDF: {pdf_path}")
    applications_text = split_into_applications(pdf_path)
    results = []
    for idx, app_text in enumerate(applications_text, 1):
        print(f"Парсинг заявки #{idx}...")
        request = parse_application(app_text)
        if request:
            results.append(convert_to_dict(request))
            print(f"  Успешно извлечено: {request.applicant.full_name}")
        else:
            print(f"  Не удалось распарсить заявку #{idx}")

    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"Результат сохранён в {output_json}")
    return results


if __name__ == "__main__":
    # Пример использования
    main("Заявки на приобретение билетов.pdf", "extracted_requests.json")