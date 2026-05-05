"""
Utilities Router — транслит, парсер билетов, переименование, структуры папок
"""
import re
import os
import json
import logging
import tempfile
from pathlib import Path
from typing import List, Optional, Dict
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/utilities", tags=["utilities"])

# ═══════════════════════════════════════════════════════════════
#  ТРАНСЛИТЕРАЦИОННЫЕ КАРТЫ (23 страны)
# ═══════════════════════════════════════════════════════════════

CIS_MAP = {
    'А':'A','Б':'B','В':'V','Г':'G','Д':'D','Е':'E','Ё':'E',
    'Ж':'ZH','З':'Z','И':'I','Й':'Y','К':'K','Л':'L','М':'M',
    'Н':'N','О':'O','П':'P','Р':'R','С':'S','Т':'T','У':'U',
    'Ф':'F','Х':'KH','Ц':'TS','Ч':'CH','Ш':'SH','Щ':'SHCH',
    'Ъ':'','Ы':'Y','Ь':'','Э':'E','Ю':'YU','Я':'YA',
    'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'e',
    'ж':'zh','з':'z','и':'i','й':'y','к':'k','л':'l','м':'m',
    'н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u',
    'ф':'f','х':'kh','ц':'ts','ч':'ch','ш':'sh','щ':'shch',
    'ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya',
}

BELARUS_MAP = {
    'А':'A','Б':'B','В':'V','Г':'H','Д':'D','Е':'E','Ё':'Yo',
    'Ж':'Zh','З':'Z','І':'I','Й':'J','К':'K','Л':'L','М':'M',
    'Н':'N','О':'O','П':'P','Р':'R','С':'S','Т':'T','У':'U',
    'Ў':'U','Ф':'F','Х':'Kh','Ц':'Ts','Ч':'C','Ш':'S','Щ':'S',
    'Ь':'','Ы':'Y','Э':'E','Ю':'Ju','Я':'Ja','И':'I',
    'а':'a','б':'b','в':'v','г':'h','д':'d','е':'e','ё':'yo',
    'ж':'zh','з':'z','і':'i','й':'j','к':'k','л':'l','м':'m',
    'н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u',
    'ў':'u','ф':'f','х':'kh','ц':'ts','ч':'c','ш':'s','щ':'s',
    'ь':'','ы':'y','э':'e','ю':'ju','я':'ja','и':'i',
}

SERBIAN_MAP = {
    'А':'A','Б':'B','В':'V','Г':'G','Д':'D','Е':'E','Ё':'E',
    'Ж':'Z','З':'Z','И':'I','Й':'J','К':'K','Л':'L','М':'M',
    'Н':'N','О':'O','П':'P','Р':'R','С':'S','Т':'T','У':'U',
    'Ф':'F','Х':'H','Ц':'C','Ч':'C','Ш':'S','Щ':'S',
    'Ъ':'','Ы':'Y','Ь':'','Э':'E','Ю':'Ju','Я':'Ja',
    'а':'a','б':'b','в':'v','г':'h','д':'d','е':'e','ё':'e',
    'ж':'z','з':'z','и':'i','й':'j','к':'k','л':'l','м':'m',
    'н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u',
    'ф':'f','х':'h','ц':'c','ч':'c','ш':'s','щ':'s',
    'ъ':'','ы':'y','ь':'','э':'e','ю':'ju','я':'ja',
}

BOSNIAN_CROATIAN_MAP = {
    'А':'A','Б':'B','В':'V','Г':'G','Д':'D','Е':'E','Ж':'Zs',
    'З':'Z','И':'I','К':'K','Л':'L','М':'M','Н':'N','О':'O',
    'П':'P','Р':'R','С':'S','Т':'T','У':'U','Ф':'F','Х':'H',
    'Ц':'C','Ч':'Cs','Ш':'S','Ё':'E','Й':'J','Ы':'Y','Ь':'',
    'Ъ':'','Э':'E','Ю':'Yu','Я':'Ya',
    'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ж':'zs',
    'з':'z','и':'i','к':'k','л':'l','м':'m','н':'n','о':'o',
    'п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'h',
    'ц':'c','ч':'cs','ш':'s','ё':'e','й':'j','ы':'y','ь':'',
    'ъ':'','э':'e','ю':'yu','я':'ya',
}

AZERBAIJAN_MAP = {
    'А':'A','а':'a','Б':'B','б':'b','В':'V','в':'v','Г':'G','г':'g',
    'Д':'D','д':'d','Е':'E','е':'e','Ё':'Yo','ё':'yo','Ж':'J','ж':'j',
    'З':'Z','з':'z','И':'I','и':'i','Й':'Y','й':'y','К':'K','к':'k',
    'Л':'L','л':'l','М':'M','м':'m','Н':'N','н':'n','О':'O','о':'o',
    'П':'P','п':'p','Р':'R','р':'r','С':'S','с':'s','Т':'T','т':'t',
    'У':'U','у':'u','Ф':'F','ф':'f','Х':'X','х':'x','Ц':'Ts','ц':'ts',
    'Ч':'Ch','ч':'ch','Ш':'Sh','ш':'sh','Щ':'Shch','щ':'shch',
    'Ы':'I','ы':'i','Ь':'','ь':'','Э':'E','э':'e','Ю':'Yu','ю':'yu',
    'Я':'Ya','я':'ya','Ъ':'','ъ':'',
}

UKRAINE_MAP = {
    'А':'A','Б':'B','В':'V','Г':'H','Ґ':'G','Д':'D','Е':'E','Є':'Ye',
    'Ж':'Zh','З':'Z','И':'Y','І':'I','Ї':'Yi','Й':'Y','К':'K','Л':'L',
    'М':'M','Н':'N','О':'O','П':'P','Р':'R','С':'S','Т':'T','У':'U',
    'Ф':'F','Х':'Kh','Ц':'Ts','Ч':'Ch','Ш':'Sh','Щ':'Shch','Ю':'Yu','Я':'Ya',
    'Ы':'Y','Э':'E','Ь':'','Ъ':'',
    'а':'a','б':'b','в':'v','г':'h','ґ':'g','д':'d','е':'e','є':'ye',
    'ж':'zh','з':'z','и':'y','і':'i','ї':'yi','й':'y','к':'k','л':'l',
    'м':'m','н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u',
    'ф':'f','х':'kh','ц':'ts','ч':'ch','ш':'sh','щ':'shch','ю':'yu','я':'ya',
    'ы':'y','э':'e','ь':'','ъ':'',
}

MACEDONIA_MAP = {
    'А':'A','Б':'B','В':'V','Г':'G','Д':'D','Е':'E','Ж':'Zh',
    'З':'Z','И':'I','К':'K','Л':'L','М':'M','Н':'N','О':'O',
    'П':'P','Р':'R','С':'S','Т':'T','У':'U','Ф':'F','Х':'H',
    'Ц':'C','Ч':'Ch','Ш':'Sh','Ё':'E','Й':'Y','Ы':'Y','Ь':'',
    'Ъ':'','Э':'E','Ю':'Yu','Я':'Ya',
    'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ж':'zh',
    'з':'z','и':'i','к':'k','л':'l','м':'m','н':'n','о':'o',
    'п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'h',
    'ц':'c','ч':'ch','ш':'sh','ё':'e','й':'y','ы':'y','ь':'',
    'ъ':'','э':'e','ю':'yu','я':'ya',
}

TRANSLIT_MAPS = {
    'Азербайджан': AZERBAIJAN_MAP,
    'Azerbaijan': AZERBAIJAN_MAP,
    'Армения': CIS_MAP,
    'Armenia': CIS_MAP,
    'Беларусь': BELARUS_MAP,
    'Belarus': BELARUS_MAP,
    'Босния': BOSNIAN_CROATIAN_MAP,
    'Bosnia': BOSNIAN_CROATIAN_MAP,
    'Хорватия': BOSNIAN_CROATIAN_MAP,
    'Croatia': BOSNIAN_CROATIAN_MAP,
    'Черногория': BOSNIAN_CROATIAN_MAP,
    'Montenegro': BOSNIAN_CROATIAN_MAP,
    'Гана': CIS_MAP,
    'Ghana': CIS_MAP,
    'Индия': CIS_MAP,
    'India': CIS_MAP,
    'Казахстан': CIS_MAP,
    'Kazakhstan': CIS_MAP,
    'Киргизия': CIS_MAP,
    'Kyrgyzstan': CIS_MAP,
    'Китай': CIS_MAP,
    'China': CIS_MAP,
    'Молдова': CIS_MAP,
    'Moldova': CIS_MAP,
    'Пакистан': CIS_MAP,
    'Pakistan': CIS_MAP,
    'Россия': CIS_MAP,
    'Российская Федерация': CIS_MAP,
    'Russia': CIS_MAP,
    'РФ': CIS_MAP,
    'РОССИЯ': CIS_MAP,
    'Северная Корея': CIS_MAP,
    'North Korea': CIS_MAP,
    'Северная Македония': MACEDONIA_MAP,
    'North Macedonia': MACEDONIA_MAP,
    'Сербия': SERBIAN_MAP,
    'Serbia': SERBIAN_MAP,
    'Сирия': CIS_MAP,
    'Syria': CIS_MAP,
    'Таджикистан': CIS_MAP,
    'Tajikistan': CIS_MAP,
    'Туркмения': CIS_MAP,
    'Turkmenistan': CIS_MAP,
    'Турция': CIS_MAP,
    'Turkey': CIS_MAP,
    'Узбекистан': CIS_MAP,
    'Uzbekistan': CIS_MAP,
    'Украина': UKRAINE_MAP,
    'Ukraine': UKRAINE_MAP,
}


def _get_map(citizenship: str) -> dict:
    c = citizenship.strip()
    if c in TRANSLIT_MAPS:
        return TRANSLIT_MAPS[c]
    c_lower = c.lower().replace(',', '').replace(' ', '')
    for key in TRANSLIT_MAPS:
        if key.lower().replace(',', '').replace(' ', '') == c_lower:
            return TRANSLIT_MAPS[key]
    return CIS_MAP


def _transliterate(text: str, trans_map: dict, uppercase: bool = True) -> str:
    result = []
    for ch in text:
        if ch in trans_map:
            result.append(trans_map[ch])
        elif re.match(r'[A-Za-z0-9\s\-]', ch):
            result.append(ch)
        elif ch in (' ', '-', '.', ','):
            result.append(ch)
    joined = ''.join(result)
    if uppercase:
        return joined.upper()
    # Title case
    return ' '.join(w.capitalize() for w in joined.split())


# ═══════════════════════════════════════════════════════════════
#  IATA коды + парсер билетов
# ═══════════════════════════════════════════════════════════════

IATA_CODES = {
    'SVO':'МОСКВА','DME':'МОСКВА','VKO':'МОСКВА','ZIA':'МОСКВА',
    'LED':'САНКТ-ПЕТЕРБУРГ','AER':'СОЧИ','KRR':'КРАСНОДАР',
    'ROV':'РОСТОВ-НА-ДОНУ','KZN':'КАЗАНЬ','UFA':'УФА',
    'KUF':'САМАРА','GOJ':'НИЖНИЙ НОВГОРОД','SVX':'ЕКАТЕРИНБУРГ',
    'CEK':'ЧЕЛЯБИНСК','TJM':'ТЮМЕНЬ','OVB':'НОВОСИБИРСК',
    'OMS':'ОМСК','KJA':'КРАСНОЯРСК','IKT':'ИРКУТСК',
    'TAS':'ТАШКЕНТ','TMJ':'ТЕРМЕЗ','BHK':'БУХАРА',
    'SKD':'САМАРКАНД','NVI':'НАВОИ','NCU':'НУКУС',
    'UGC':'УРГЕНЧ','FEG':'ФЕРГАНА','KSQ':'КАРШИ',
    'AZN':'АНДИЖАН','NMA':'НАМАНГАН','ALA':'АЛМАТЫ',
    'NQZ':'АСТАНА','CIT':'ШЫМКЕНТ','MSQ':'МИНСК',
    'EVN':'ЕРЕВАН','GYD':'БАКУ','TBS':'ТБИЛИСИ',
    'FRU':'БИШКЕК','DYU':'ДУШАНБЕ','LBD':'ХУДЖАНД',
    'IST':'СТАМБУЛ','SAW':'СТАМБУЛ','AYT':'АНТАЛЬЯ',
    'DXB':'ДУБАЙ','AUH':'АБУ-ДАБИ',
}

IATA_TO_CARRIER = {
    'HY':'UZBEKISTAN AIRWAYS','KC':'AIR ASTANA','DV':'SCAT AIRLINES',
    'SU':'AEROFLOT','S7':'S7 AIRLINES','U6':'URAL AIRLINES',
    'DP':'POBEDA','A4':'AZIMUT','B2':'BELAVIA','TK':'TURKISH AIRLINES',
    'PC':'PEGASUS AIRLINES','XQ':'SUNEXPRESS','LH':'LUFTHANSA',
    'AF':'AIR FRANCE','BA':'BRITISH AIRWAYS','EK':'EMIRATES',
    'EY':'ETIHAD AIRWAYS','QR':'QATAR AIRWAYS','FZ':'FLY DUBAI',
    'AA':'AMERICAN AIRLINES','DL':'DELTA AIR LINES','UA':'UNITED AIRLINES',
    'FR':'RYANAIR','U2':'EASYJET','W6':'WIZZ AIR',
}

MONTH_MAP = {
    'JAN':'01','FEB':'02','MAR':'03','APR':'04','MAY':'05','JUN':'06',
    'JUL':'07','AUG':'08','SEP':'09','OCT':'10','NOV':'11','DEC':'12',
    'ЯНВ':'01','ФЕВ':'02','МАР':'03','АПР':'04','МАЙ':'05','ИЮН':'06',
    'ИЮЛ':'07','АВГ':'08','СЕН':'09','ОКТ':'10','НОЯ':'11','ДЕК':'12',
    'MAP':'03',
}


def _parse_ticket_text(text: str, filename: str) -> dict:
    data = {'source_file': filename}
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    text_up = text.upper()

    # Пассажир
    name_m = re.match(r'^([А-ЯЁA-Z][А-ЯЁа-яёA-Za-z]+ [А-ЯЁA-Z][А-ЯЁа-яёA-Za-z]+)', filename)
    data['passenger'] = name_m.group(1) if name_m else 'Не указано'

    # Номер билета
    tkt = re.search(r'НОМЕР БИЛЕТА\s*:\s*(\d+\s+\d+)', text)
    data['ticket_number'] = tkt.group(1).replace(' ', '') if tkt else 'Не указано'

    # Номер заказа
    order_m = re.search(r'-\s*([A-Z0-9]{6,})', filename)
    data['order_number'] = order_m.group(1) if order_m else 'Не указано'

    # Дата выдачи
    d_issue = re.search(r'ДАТА:\s*(\d{2})([А-ЯA-Z]{3})(\d{2})', text)
    if d_issue:
        dd, mm_s, yy = d_issue.groups()
        mm = MONTH_MAP.get(mm_s[:3].upper(), '01')
        data['issue_date'] = f"{dd}.{mm}.20{yy}"
    else:
        data['issue_date'] = 'Не указано'

    # Перевозчик
    carrier = 'Не указано'
    for code, name in IATA_TO_CARRIER.items():
        if name in text_up:
            carrier = name
            break
    if carrier == 'Не указано':
        flight_m = re.search(r'\b([A-Z]{2})\s*\d{3,4}\b', text)
        if flight_m:
            c = flight_m.group(1)
            carrier = IATA_TO_CARRIER.get(c, c)
    data['carrier'] = carrier

    # Номер рейса
    fn_m = re.search(r'\b([A-Z]{2})\s*(\d{3,4})\b', text)
    data['flight_number'] = f"{fn_m.group(1)}{fn_m.group(2)}" if fn_m else 'Не указано'

    # Маршрут
    iata_codes_in_text = re.findall(r'\b([A-Z]{3})\b', text)
    exclude = {'NUC','ROE','RUB','EUR','USD','END','MOW','PC','NDC'}
    valid_codes = [c for c in iata_codes_in_text if c not in exclude and c in IATA_CODES]
    if len(valid_codes) >= 2:
        dep = IATA_CODES.get(valid_codes[0], valid_codes[0])
        arr = IATA_CODES.get(valid_codes[-1], valid_codes[-1])
        data['route'] = f"{dep} - {arr}"
        data['arrival_airport'] = f"{arr} ({valid_codes[-1]})"
    else:
        # Try RU pattern
        route_m = re.search(r'([А-Яа-я]+)\s*[–—\-]\s*([А-Яа-я]+)', text)
        if route_m:
            data['route'] = f"{route_m.group(1).upper()} - {route_m.group(2).upper()}"
        else:
            data['route'] = 'Не указано'
        data['arrival_airport'] = 'Не указано'

    # Даты/время
    time_m = re.search(r'(\d{2})([А-ЯA-Z]{3})\s+(\d{2})(\d{2})\s+(\d{2})(\d{2})', text)
    if time_m:
        day, mm_s, dh, dm, ah, am = time_m.groups()
        mm = MONTH_MAP.get(mm_s[:3].upper(), '01')
        yr = data['issue_date'].split('.')[-1] if '.' in data.get('issue_date','') else '2026'
        data['departure_time'] = f"{dh}:{dm}"
        data['arrival_time'] = f"{ah}:{am}"
        data['departure_date'] = f"{day}.{mm}.{yr}"
        data['arrival_date'] = data['departure_date']
    else:
        data['departure_time'] = data['arrival_time'] = 'Не указано'
        data['departure_date'] = data['arrival_date'] = 'Не указано'

    # Стоимость
    price_m = re.search(r'ИТОГО[^:]*:\s*(?:RUB\s*)?(\d[\d\s]*)', text, re.I)
    if price_m:
        data['total_price'] = price_m.group(1).replace(' ', '')
        data['currency'] = 'RUB'
    else:
        data['total_price'] = 'Не указано'
        data['currency'] = 'RUB'

    return data


# ═══════════════════════════════════════════════════════════════
#  ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.post("/translit")
def transliterate_fio(data: dict):
    """
    Транслитерация ФИО на 23 страны.
    data: { rows: [ {fio, citizenship}, ... ], uppercase: true }
    """
    rows = data.get('rows', [])
    uppercase = data.get('uppercase', True)
    results = []
    for row in rows:
        fio = str(row.get('fio', '')).strip()
        citizenship = str(row.get('citizenship', 'Россия')).strip()
        if not fio:
            results.append({'fio': fio, 'citizenship': citizenship, 'result': ''})
            continue
        trans_map = _get_map(citizenship)
        transliterated = _transliterate(fio, trans_map, uppercase=uppercase)
        results.append({
            'fio': fio,
            'citizenship': citizenship,
            'result': transliterated,
        })
    return {'results': results}


@router.get("/translit/countries")
def get_countries():
    """Список поддерживаемых стран."""
    return {'countries': sorted(set(TRANSLIT_MAPS.keys()))}


@router.post("/translit/export")
def export_translit(data: dict):
    """Экспорт результатов транслитерации в Excel."""
    import pandas as pd
    from io import BytesIO

    rows = data.get('rows', [])
    if not rows:
        raise HTTPException(400, "Нет данных")

    df = pd.DataFrame(rows, columns=['Гражданство', 'ФИО (RU)', 'ФИО (EN)'])
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Транслит')
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': 'attachment; filename="translit_result.xlsx"'}
    )


@router.post("/parse-tickets-pdf")
async def parse_tickets_pdf(files: list[UploadFile] = File(...)):
    """Парсинг PDF авиабилетов."""
    results = []
    for file in files:
        content = await file.read()
        suffix = os.path.splitext(file.filename)[1] or '.pdf'
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(content)
            tmp_path = f.name
        try:
            text = _extract_pdf_text(tmp_path)
            parsed = _parse_ticket_text(text, Path(file.filename).stem)
            results.append({'filename': file.filename, 'data': parsed, 'ok': True})
        except Exception as e:
            results.append({'filename': file.filename, 'error': str(e), 'ok': False})
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
    return {'results': results, 'total': len(results)}


def _extract_pdf_text(pdf_path: str) -> str:
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            return '\n'.join(page.extract_text() or '' for page in pdf.pages)
    except ImportError:
        pass
    try:
        import PyPDF2
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            return '\n'.join(page.extract_text() or '' for page in reader.pages)
    except ImportError:
        pass
    return ''


@router.post("/parse-tickets-pdf/export")
def export_tickets_excel(data: dict):
    """Экспорт распарсенных билетов в Excel."""
    import pandas as pd
    from io import BytesIO

    tickets = data.get('tickets', [])
    if not tickets:
        raise HTTPException(400, "Нет данных")

    cols_ru = {
        'passenger': 'Пассажир',
        'ticket_number': 'Номер билета',
        'order_number': 'Номер заказа',
        'issue_date': 'Дата выдачи',
        'carrier': 'Перевозчик',
        'flight_number': 'Номер рейса',
        'departure_time': 'Время вылета',
        'departure_date': 'Дата вылета',
        'route': 'Маршрут',
        'arrival_airport': 'Аэропорт прибытия',
        'arrival_time': 'Время прилета',
        'arrival_date': 'Дата прилета',
        'total_price': 'Стоимость',
        'currency': 'Валюта',
        'source_file': 'Источник',
    }
    rows = []
    for t in tickets:
        rows.append({v: t.get(k, '') for k, v in cols_ru.items()})

    df = pd.DataFrame(rows)
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Билеты')
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': 'attachment; filename="tickets_parsed.xlsx"'}
    )


@router.post("/rename-preview")
def rename_preview(data: dict):
    """
    Предварительный просмотр переименования файлов по шаблону.
    data: { files: [str, ...], mode: 'pattern'|'replace'|'prefix_suffix'|'case',
            pattern: str, start: int, find: str, replace: str, prefix: str, suffix: str, case: str }
    """
    files = data.get('files', [])
    mode = data.get('mode', 'pattern')
    results = []

    for i, old_name in enumerate(files):
        stem = Path(old_name).stem
        ext = Path(old_name).suffix

        if mode == 'pattern':
            pattern = data.get('pattern', '{n}')
            start = int(data.get('start', 1))
            n = start + i
            new_stem = pattern.replace('{n}', str(n)).replace('{name}', stem).replace('{i}', str(i+1))
            new_name = new_stem + ext

        elif mode == 'replace':
            find = data.get('find', '')
            repl = data.get('replace', '')
            new_stem = stem.replace(find, repl) if find else stem
            new_name = new_stem + ext

        elif mode == 'prefix_suffix':
            prefix = data.get('prefix', '')
            suffix = data.get('suffix', '')
            new_name = prefix + stem + suffix + ext

        elif mode == 'case':
            case = data.get('case', 'title')
            if case == 'upper':
                new_stem = stem.upper()
            elif case == 'lower':
                new_stem = stem.lower()
            elif case == 'title':
                new_stem = stem.title()
            else:
                new_stem = stem
            new_name = new_stem + ext

        else:
            new_name = old_name

        results.append({'old': old_name, 'new': new_name})

    return {'results': results}


@router.post("/stazh")
def calc_stazh(data: dict):
    """Расчёт стажа сотрудников из базы."""
    from hr_app.backend.database import get_conn
    from datetime import datetime

    with get_conn() as conn:
        rows = conn.execute(
            "SELECT fio, tab_num, hire_date, fire_date, status, department FROM employees "
            "WHERE hire_date != '' ORDER BY hire_date"
        ).fetchall()

    today = datetime.today()
    results = []
    for r in rows:
        try:
            d, m, y = r['hire_date'].split('.')
            hire = datetime(int(y), int(m), int(d))
        except Exception:
            continue

        end = today
        if r['fire_date']:
            try:
                fd, fm, fy = r['fire_date'].split('.')
                end = datetime(int(fy), int(fm), int(fd))
            except Exception:
                pass

        years = (end - hire).days / 365.25
        results.append({
            'fio': r['fio'],
            'tab_num': r['tab_num'],
            'hire_date': r['hire_date'],
            'fire_date': r['fire_date'] or '',
            'status': r['status'],
            'department': r['department'],
            'years': round(years, 2),
        })

    results.sort(key=lambda x: -x['years'])
    avg = round(sum(r['years'] for r in results) / len(results), 2) if results else 0
    return {'results': results[:2000], 'total': len(results), 'avg_years': avg}


@router.post("/stazh/export")
def export_stazh(data: dict):
    """Экспорт стажа в Excel."""
    import pandas as pd
    from io import BytesIO

    rows = data.get('rows', [])
    if not rows:
        raise HTTPException(400, "Нет данных")

    df = pd.DataFrame(rows)
    if 'years' in df.columns:
        df = df.rename(columns={
            'fio': 'ФИО', 'tab_num': 'Табном', 'hire_date': 'Дата приёма',
            'fire_date': 'Дата увольнения', 'status': 'Статус',
            'department': 'Подразделение', 'years': 'Стаж (лет)'
        })
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Стаж')
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': 'attachment; filename="stazh.xlsx"'}
    )
