# ticket_app/database.py
import re
import hashlib
import logging
import os
from typing import Optional, List, Dict, Tuple

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

_EMPLOYEES_DB: Optional[pd.DataFrame] = None


def safe_str(value, default: str = "") -> str:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    result = str(value).strip()
    return default if result in ("nan", "None", "") else result


def normalize_fio(fio: str) -> str:
    return ' '.join(re.sub(r'[.,;]', '', str(fio)).split())


def hash_fio(fio: str) -> str:
    return hashlib.md5(normalize_fio(fio).lower().encode()).hexdigest()


def _find_column(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    for col in df.columns:
        col_clean = col.strip().lower().replace('.', '').replace(' ', '').replace('_', '')
        for name in candidates:
            name_clean = name.lower().replace('.', '').replace(' ', '').replace('_', '')
            if name_clean in col_clean or col_clean in name_clean:
                return col
    return None


def set_employees_db(df: pd.DataFrame):
    global _EMPLOYEES_DB
    _EMPLOYEES_DB = df


def get_employees_db() -> Optional[pd.DataFrame]:
    return _EMPLOYEES_DB


def get_all_employees() -> List[Dict]:
    return _EMPLOYEES_DB.to_dict('records') if _EMPLOYEES_DB is not None else []


# Дополнительные данные из Базы
_PASSWORDS_DB: List[Dict] = []       # лист ПАРОЛЬ
_ROUTES_DB: List[Dict] = []          # лист МАРШРУТ
_RESPONSIBLE_DB: List[Dict] = []     # лист ОТВЕТСТВЕННЫЙ


def get_passwords_db() -> List[Dict]:
    return _PASSWORDS_DB


def get_routes_for_department(department: str) -> List[str]:
    """Возвращает маршруты для подразделения (приоритетные + общие)."""
    priority, general = [], []
    for row in _ROUTES_DB:
        dept = row.get('department', '')
        route = row.get('route', '')
        if not route:
            continue
        if dept and dept.strip().lower() in department.lower():
            priority.append(route)
        else:
            general.append(route)
    # приоритетные маршруты сверху, затем общие без дублей
    seen = set(priority)
    result = list(priority)
    for r in general:
        if r not in seen:
            result.append(r)
            seen.add(r)
    return result


def get_transfer_city_for_route(route: str, department: str) -> str:
    """Возвращает город пересадки для маршрута из листа МАРШРУТ."""
    for row in _ROUTES_DB:
        dept = row.get('department', '')
        if dept and dept.strip().lower() not in department.lower():
            continue
        if row.get('route', '') == route:
            return row.get('transfer', '')
    return ''


def get_responsible_for_department(department: str) -> List[str]:
    """Возвращает список ответственных для подразделения."""
    result = []
    for row in _RESPONSIBLE_DB:
        dept = row.get('department', '')
        if dept and dept.strip().lower() in department.lower():
            name = row.get('responsible', '')
            if name and name not in result:
                result.append(name)
    return result


def get_responsible_info(responsible_name: str, department: str) -> Dict:
    """Возвращает ФИО, должность, отдел ответственного."""
    for row in _RESPONSIBLE_DB:
        dept = row.get('department', '')
        if dept and dept.strip().lower() not in department.lower():
            continue
        if row.get('responsible', '') == responsible_name:
            return {
                'fio': row.get('fio', ''),
                'position': row.get('position', ''),
                'dept_category': row.get('dept_category', ''),
            }
    return {}


def load_employees_base(file_path: str) -> Tuple[bool, str, int]:
    global _EMPLOYEES_DB, _PASSWORDS_DB, _ROUTES_DB, _RESPONSIBLE_DB
    if not os.path.exists(file_path):
        return False, f"Файл не найден: {file_path}", 0
    try:
        xl = pd.ExcelFile(file_path)

        # --- Лист ПАРОЛЬ ---
        if 'ПАРОЛЬ' in xl.sheet_names:
            df_pwd = pd.read_excel(file_path, sheet_name='ПАРОЛЬ', header=0)
            df_pwd.columns = df_pwd.columns.str.strip()
            _PASSWORDS_DB = [
                {
                    'department': safe_str(r.iloc[0]),
                    'password':   safe_str(r.iloc[1]),
                    'access':     safe_str(r.iloc[2]) if len(r) > 2 else '',
                }
                for _, r in df_pwd.iterrows() if safe_str(r.iloc[0])
            ]

        # --- Лист МАРШРУТ ---
        if 'МАРШРУТ' in xl.sheet_names:
            df_rt = pd.read_excel(file_path, sheet_name='МАРШРУТ', header=0)
            df_rt.columns = df_rt.columns.str.strip()
            _ROUTES_DB = [
                {
                    'department': safe_str(r.iloc[0]),
                    'route':      safe_str(r.iloc[1]),
                    'transfer':   safe_str(r.iloc[2]) if len(r) > 2 else '',
                }
                for _, r in df_rt.iterrows() if safe_str(r.iloc[1])
            ]

        # --- Лист ОТВЕТСТВЕННЫЙ ---
        if 'ОТВЕТСТВЕННЫЙ' in xl.sheet_names:
            df_resp = pd.read_excel(file_path, sheet_name='ОТВЕТСТВЕННЫЙ', header=0)
            df_resp.columns = df_resp.columns.str.strip()
            _RESPONSIBLE_DB = [
                {
                    'department':    safe_str(r.iloc[0]),
                    'responsible':   safe_str(r.iloc[1]),
                    'fio':           safe_str(r.iloc[2]) if len(r) > 2 else '',
                    'position':      safe_str(r.iloc[3]) if len(r) > 3 else '',
                    'dept_category': safe_str(r.iloc[4]) if len(r) > 4 else '',
                }
                for _, r in df_resp.iterrows() if safe_str(r.iloc[0])
            ]

        # --- Лист ВСЕ ОП ---
        df = None
        used_sheet = None
        for sheet in ["ВСЕ ОП", "Sheet1", "Employees", "Сотрудники"]:
            if sheet in xl.sheet_names:
                df = pd.read_excel(file_path, sheet_name=sheet, header=0)
                used_sheet = sheet
                break
        if df is None:
            df = pd.read_excel(file_path, sheet_name=0, header=0)
            used_sheet = xl.sheet_names[0]

        df.columns = df.columns.str.strip()
        cols = list(df.columns)

        # Маппинг по позиции столбца (J=9, O=14, индексация с 0)
        # Приоритет: сначала по имени, потом по позиции
        col_map = {
            'fio':                 ['ФИО', 'Ф.И.О.', 'FIO', 'фио', 'ФИО сотрудника'],
            'tab_num':             ['Табельный номер', 'Таб№', 'Таб.№', 'tab_num', 'Табельный'],
            'position':            ['Должность', 'Position', 'Должность сотрудника'],
            'department':          ['Подразделение', 'Department'],
            'department_category': ['Отдел', 'Отдел (СМУ', 'department_category'],
            'citizenship':         ['Страна гражданства', 'Гражданство', 'Citizenship'],
            'birth_date':          ['Дата рождения', 'BirthDate', 'Д.рождения'],
            'doc_series':          ['Серия', 'Series', 'Серия документа', 'Удостоверение.Серия'],
            'doc_num':             ['Номер документа', 'Номер паспорта', 'Number', 'Удостоверение.Номер'],
            'doc_date':            ['Дата выдачи', 'DocDate', 'Удостоверение.Дата выдачи'],
            'doc_expiry':          ['Дата окончания', 'Срок действия', 'doc_expiry'],
            'doc_issuer':          ['Кем выдан', 'Issuer', 'Удостоверение.Кем выдан'],
            'address':             ['Место постоянного проживания', 'Адрес', 'Address',
                                    'Физическое лицо.Адрес по прописке'],
            'phone':               ['Телефон', 'Phone', 'Мобильный',
                                    'Физическое лицо.Личный мобильный телефон'],
        }

        mapping = {}
        for field, candidates in col_map.items():
            col = _find_column(df, candidates)
            if col:
                mapping[col] = field

        # Позиционный fallback по индексу столбца (только если поле не найдено по имени)
        # J=9 -> tab_num, O=14 -> doc_num  (индексация с 0)
        mapped_fields = set(mapping.values())
        COL_POS_FALLBACK = {9: 'tab_num', 14: 'doc_num'}
        for pos, field in COL_POS_FALLBACK.items():
            if field not in mapped_fields and pos < len(cols):
                col_name = cols[pos]
                if col_name not in mapping:
                    mapping[col_name] = field
                    logger.info("Позиционный fallback: столбец %s (%s) -> %s", pos, col_name, field)

        df = df.rename(columns=mapping)
        needed = [c for c in col_map.keys() if c in df.columns]
        df = df[needed]
        df['fio'] = df['fio'].apply(safe_str)
        df = df[df['fio'].notna() & (df['fio'] != '') & (df['fio'] != 'nan')]
        df['fio_hash'] = df['fio'].apply(hash_fio)
        for col in df.columns:
            if col not in ('fio', 'fio_hash'):
                df[col] = df[col].apply(lambda x: safe_str(x, ""))

        _EMPLOYEES_DB = df.reset_index(drop=True)
        return True, f"Загружено {len(df)} сотрудников (лист: {used_sheet})", len(df)
    except Exception as e:
        logger.exception("Ошибка загрузки базы")
        return False, f"Ошибка загрузки: {e}", 0


def find_employee_by_fio(fio: str, department_filter: str = None) -> Tuple[Optional[object], str]:
    if _EMPLOYEES_DB is None:
        return None, 'not_found'

    fio_hash = hash_fio(fio)
    matches = _EMPLOYEES_DB[_EMPLOYEES_DB['fio_hash'] == fio_hash]

    if len(matches) == 1:
        return matches.iloc[0].to_dict(), 'found'

    if len(matches) > 1:
        if department_filter:
            filtered = matches[matches['department'].str.contains(
                department_filter, na=False, case=False)]
            if len(filtered) == 1:
                return filtered.iloc[0].to_dict(), 'found'
            if len(filtered) > 1:
                return filtered.to_dict('records'), 'multiple'
        return matches.to_dict('records'), 'multiple'

    # Частичный поиск
    parts = normalize_fio(fio).lower().split()
    if len(parts) >= 2:
        mask = pd.Series([False] * len(_EMPLOYEES_DB), index=_EMPLOYEES_DB.index)
        for part in parts:
            mask |= _EMPLOYEES_DB['fio'].str.lower().str.contains(part, na=False)
        matches = _EMPLOYEES_DB[mask]
        if len(matches) == 1:
            return matches.iloc[0].to_dict(), 'found'
        if len(matches) > 1:
            return matches.to_dict('records'), 'multiple'

    return None, 'not_found'


def find_employee_by_tab_num(tab_num: str) -> Optional[Dict]:
    if _EMPLOYEES_DB is None or not tab_num:
        return None
    matches = _EMPLOYEES_DB[_EMPLOYEES_DB['tab_num'] == tab_num]
    return matches.iloc[0].to_dict() if len(matches) > 0 else None
