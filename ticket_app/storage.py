# ticket_app/storage.py
import json
import logging
import os
from datetime import datetime
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)
DB_STORAGE_FILE = "employees_database.json"


def save_database_to_file(df: Optional[pd.DataFrame]) -> bool:
    if df is None or df.empty:
        return False
    try:
        save_data = {
            "saved_at": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
            "total_count": len(df),
            "employees": df.to_dict(orient='records'),
        }
        with open(DB_STORAGE_FILE, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error("Ошибка сохранения базы: %s", e)
        return False


def load_database_from_file() -> Optional[pd.DataFrame]:
    if not os.path.exists(DB_STORAGE_FILE):
        return None
    try:
        with open(DB_STORAGE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        employees = data.get("employees", [])
        if not employees:
            return None
        df = pd.DataFrame(employees)
        df = df[df['fio'].notna() & (df['fio'] != '') & (df['fio'] != 'nan')]
        return df.reset_index(drop=True)
    except Exception as e:
        logger.error("Ошибка загрузки базы: %s", e)
        return None
