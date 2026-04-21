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


def load_employees_base(file_path: str) -> Tuple[bool, str, int]:
    global _EMPLOYEES_DB
    if not os.path.exists(file_path):
        return False, f"Файл не найден: {file_path}", 0
    try:
        xl = pd.ExcelFile(file_path)
        df = None
        used_sheet = None
        for sheet in ["ВСЕ ОП", "Sheet1", "Employees", "Сотрудники"]:
            if sheet in xl.sheet_names:
                df = pd.read_excel(file_path, sheet_name=sheet)
                used_sheet = sheet
                break
        if df is None:
            df = pd.read_excel(file_path, sheet_name=0)
            used_sheet = xl.sheet_names[0]

        df.columns = df.columns.str.strip()

        mapping = {}
        col_map = {
            'fio':                 ['ФИО', 'Ф.И.О.', 'FIO', 'фио'],
            'tab_num':             ['Таб№', 'Табельный', 'tab_num', 'Табельный номер'],
            'position':            ['Должность', 'Position'],
            'department':          ['Подразделение', 'Department'],
            'department_category': ['Отдел', 'Отдел (СМУ, УМиТ, ОТиЗ)', 'department_category'],
            'citizenship':         ['Страна гражданства', 'Гражданство', 'Citizenship'],
            'birth_date':          ['Дата рождения', 'BirthDate'],
            'doc_series':          ['Серия', 'Series', 'Удостоверение.Серия'],
            'doc_num':             ['Номер', 'Number', 'Удостоверение.Номер'],
            'doc_date':            ['Дата выдачи', 'DocDate', 'Удостоверение.Дата выдачи'],
            'doc_expiry':          ['Дата окончания', 'Срок действия', 'doc_expiry'],
            'doc_issuer':          ['Кем выдан', 'Issuer', 'Удостоверение.Кем выдан'],
            'address':             ['Место постоянного проживания', 'Адрес', 'Address',
                                    'Физическое лицо.Адрес по прописке'],
            'phone':               ['Телефон', 'Phone', 'Мобильный',
                                    'Физическое лицо.Личный мобильный телефон'],
        }
        for field, candidates in col_map.items():
            col = _find_column(df, candidates)
            if col:
                mapping[col] = field

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
