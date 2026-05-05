"""
Excel Service — загрузка и обработка Excel файлов
"""
import re
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

import pandas as pd
import numpy as np

from hr_app.backend.database import (
    upsert_employees, log_action, save_ticket_orders, get_setting
)

logger = logging.getLogger(__name__)


def safe_str(val, default="") -> str:
    if val is None:
        return default
    try:
        if pd.isna(val):
            return default
    except (TypeError, ValueError):
        pass
    s = str(val).strip()
    return default if s in ("nan", "None", "NaT", "") else s


def safe_date(val) -> str:
    """Приводит дату к формату ДД.ММ.ГГГГ."""
    s = safe_str(val)
    if not s:
        return ""
    # Already formatted
    if re.match(r'^\d{2}\.\d{2}\.\d{4}$', s):
        return s
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d",
                "%d-%m-%Y", "%Y-%m-%dT%H:%M:%S", "%d.%m.%Y %H:%M:%S"):
        try:
            return datetime.strptime(s[:10], fmt[:len(fmt)]).strftime("%d.%m.%Y")
        except ValueError:
            pass
    m = re.search(r'(\d{1,2})[./-](\d{1,2})[./-](\d{4})', s)
    if m:
        d, mo, y = m.groups()
        return f"{d.zfill(2)}.{mo.zfill(2)}.{y}"
    return s


# Column index → field name (0-based, columns A=0, B=1, ...)
# Based on the БАЗА.xlsx description
_COL_BY_POS = {
    0:  "unique1",        # A
    1:  "unique2",        # B
    2:  "tab_num",        # C
    3:  "org",            # D
    4:  "territory",      # E
    5:  "fio",            # F
    6:  "citizenship",    # G
    7:  "birth_date",     # H
    8:  "doc_series",     # I
    9:  "doc_num",        # J
    10: "position",       # K
    11: "grade",          # L
    12: "department",     # M
    13: "section",        # N
    14: "section2",       # O
    15: "work_schedule",  # P
    16: "hire_date",      # Q
    17: "fire_date",      # R
    18: "status",         # S
    19: "work_start_date",# T
    20: "birth_place",    # U
    21: "doc_issuer",     # V
    22: "doc_issue_date", # W
    23: "address",        # X
    24: "phone_home",     # Y
    25: "phone_mobile",   # Z
    26: "phone_work",     # AA
    27: "total",          # AB
    28: "region_eju",     # AC
    29: "platform_eju",   # AD
    30: "position_eju",   # AE
    31: "section_eju",    # AF
    32: "section2_eju",   # AG
    33: "visa_eju",       # AH
    34: "visa_type_eju",  # AI
    35: "visa_region_eju",# AJ
    36: "visa_expire_eju",# AK
    37: "shift_start_eju",# AL
    38: "status_op",      # AM
    39: "subdivision_blt",# AN  (placeholder, filled from settings)
    40: "classification",  # AO
    41: "dept_category",  # AP
    42: "doc_type",       # AQ
}

_NAME_MAP = {
    "фио+датарождения_unique1": "unique1",
    "объединенный_номер_unique2": "unique2",
    "табельный_номер_unique3": "tab_num",
    "организация_1с": "org",
    "территория_1с": "territory",
    "фио_1с": "fio",
    "гражданство_1с": "citizenship",
    "дата_рождения_1с": "birth_date",
    "удостоверениесерия_1с": "doc_series",
    "удостоверениесерия": "doc_series",
    "удостоверениеномер_1с": "doc_num",
    "удостоверениеномер": "doc_num",
    "должность_1с": "position",
    "разряд_1с": "grade",
    "подразделение_1с": "department",
    "участок_отдел_1с": "section",
    "участок_отдел2_1с": "section2",
    "график_работы_1с": "work_schedule",
    "дата_приема_1с": "hire_date",
    "дата_увольнения_1с": "fire_date",
    "статус_сотрудника_1с": "status",
    "сотрудникдата_выхода_на_работу_1с": "work_start_date",
    "место_рождения_1с": "birth_place",
    "удостоверениекем_выдан_1с": "doc_issuer",
    "удостоверениедата выдачи_1с": "doc_issue_date",
    "удостоверениедата_выдачи_1с": "doc_issue_date",
    "физическое_лицоадрес_по_прописке_1с": "address",
    "физическое_лицодомашний_телефон_1с": "phone_home",
    "физическое_лицоличный_мобильный_телефон_1с": "phone_mobile",
    "физическое_лицорабочий_телефон_1с": "phone_work",
    "итого_1с": "total",
    "регион_ежу": "region_eju",
    "площадка_ежу": "platform_eju",
    "фактическая_должность_ежу": "position_eju",
    "фактический_участок_отдел_ежу": "section_eju",
    "фактический_участок_отдел2_ежу": "section2_eju",
    "виза_ежу": "visa_eju",
    "вид_визы_ежу": "visa_type_eju",
    "регион_визы_ежу": "visa_region_eju",
    "срок_до_ежу": "visa_expire_eju",
    "дата_начала_вахты_прием_на_работу_ежу": "shift_start_eju",
    "статус_оп": "status_op",
    "статус_ оп": "status_op",
    "подразделение_блт": "subdivision_blt",
    "классификация_сотрудников_(итр_или_рабочие)_блт": "classification",
    "классификация_сотрудников_итр_или_рабочие_блт": "classification",
    "отдел_(сму,_умит,_отиз)_и_т.д_блт": "dept_category",
    "вид_документа_блт": "doc_type",
}


def _normalize_col(col: str) -> str:
    """Нормализует имя столбца для сопоставления."""
    col = str(col).strip().lower()
    col = col.replace(" ", "_").replace(".", "").replace(",", "").replace("(", "").replace(")", "")
    return col


def _map_df_columns(df: pd.DataFrame) -> Dict[str, str]:
    """Returns mapping: df_column_name -> field_name"""
    mapping = {}
    for col in df.columns:
        normalized = _normalize_col(col)
        if normalized in _NAME_MAP:
            mapping[col] = _NAME_MAP[normalized]
    return mapping


def load_main_base(file_path: str) -> Tuple[bool, str, int]:
    """Загрузка основной базы БАЗА.xlsx лист База_1С"""
    try:
        logger.info("Loading main base from %s", file_path)
        xl = pd.ExcelFile(file_path)

        # Find the correct sheet
        sheet = None
        for candidate in ["База_1С", "База_1С ", "ВСЕ ОП", "Sheet1", "Лист1"]:
            if candidate in xl.sheet_names:
                sheet = candidate
                break
        if sheet is None:
            sheet = xl.sheet_names[0]

        df = pd.read_excel(file_path, sheet_name=sheet, header=0, dtype=str)
        df.columns = df.columns.astype(str)

        # Map columns by name
        col_map = _map_df_columns(df)

        # Fallback: map by position
        for pos_idx, field in _COL_BY_POS.items():
            if pos_idx < len(df.columns):
                col = df.columns[pos_idx]
                if col not in col_map and field not in col_map.values():
                    col_map[col] = field

        # Rename
        df = df.rename(columns=col_map)

        # Keep only known fields
        known_fields = set(_COL_BY_POS.values())
        df = df[[c for c in df.columns if c in known_fields]]

        # Ensure fio exists
        if "fio" not in df.columns:
            return False, "Не найден столбец ФИО (F / ФИО_1С)", 0

        # Clean up
        for col in df.columns:
            df[col] = df[col].apply(safe_str)

        # Date columns
        for date_col in ["birth_date", "hire_date", "fire_date", "doc_issue_date",
                         "work_start_date", "shift_start_eju", "visa_expire_eju"]:
            if date_col in df.columns:
                df[date_col] = df[date_col].apply(safe_date)

        # Filter empty FIO
        df = df[df["fio"].notna() & (df["fio"] != "")]

        records = df.to_dict("records")
        count = upsert_employees(records)
        log_action("load_main_base", os.path.basename(file_path), count, "ok")
        return True, f"Загружено {count} сотрудников (лист: {sheet})", count

    except Exception as e:
        logger.exception("Error loading main base")
        log_action("load_main_base", os.path.basename(file_path), 0, "error", str(e))
        return False, f"Ошибка загрузки: {e}", 0


def load_daily_tracking_files(folder_path: str, track_date: str) -> Tuple[bool, str, int]:
    """
    Загружает файлы Ежедневного учёта из папки.
    Ищет все *.xls* файлы, читает лист 'ЕЖЕДНЕВНЫЙ УЧЕТ',
    фильтрует красные строки, объединяет данные.
    """
    from hr_app.backend.database import get_conn
    import openpyxl

    folder = Path(folder_path)
    if not folder.exists():
        return False, f"Папка не найдена: {folder_path}", 0

    files = list(folder.glob("*.xls*")) + list(folder.glob("*.xlsb"))
    if not files:
        return False, "Файлы Excel не найдены в папке", 0

    RED_COLORS = {
        (255, 0, 0), (255, 199, 206)
    }

    all_rows = []
    processed = 0
    skipped = 0

    for fp in files:
        try:
            wb = openpyxl.load_workbook(str(fp), read_only=False, data_only=True)
            sheet_found = None
            for sname in wb.sheetnames:
                if sname.strip().upper() == "ЕЖЕДНЕВНЫЙ УЧЕТ":
                    sheet_found = sname
                    break

            if not sheet_found:
                skipped += 1
                continue

            ws = wb[sheet_found]
            rows_data = []
            for row_idx, row in enumerate(ws.iter_rows(min_row=6, values_only=False), start=6):
                # Check cell E (index 4) not empty
                cell_e = row[4] if len(row) > 4 else None
                if cell_e is None or cell_e.value is None or str(cell_e.value).strip() == "":
                    break

                # Check fill color (red = skip)
                skip_row = False
                for cell in row[:16]:
                    fill = cell.fill
                    if fill and fill.fgColor and fill.fgColor.type == "rgb":
                        rgb_hex = fill.fgColor.rgb
                        if len(rgb_hex) == 8:
                            r = int(rgb_hex[2:4], 16)
                            g = int(rgb_hex[4:6], 16)
                            b = int(rgb_hex[6:8], 16)
                            if (r, g, b) in RED_COLORS or (r == 255 and g == 0 and b == 0):
                                skip_row = True
                                break
                if skip_row:
                    continue

                vals = [cell.value for cell in row[:16]]
                rows_data.append(vals)

            wb.close()

            # Map columns: A=0 region, B=1 platform, C=2 fio(?), D=3 tab_num, J=9 position...
            for vals in rows_data:
                while len(vals) < 16:
                    vals.append(None)
                all_rows.append({
                    "track_date": track_date,
                    "source_file": fp.name,
                    "region": safe_str(vals[1]),      # B
                    "platform": safe_str(vals[2]),    # C
                    "tab_num": safe_str(vals[3]),     # D
                    "fio": safe_str(vals[4]),         # E
                    "position": safe_str(vals[9]),    # J
                    "section": safe_str(vals[10]),    # K
                    "visa": safe_str(vals[11]),       # L
                    "visa_type": safe_str(vals[12]),  # M
                    "visa_region": safe_str(vals[13]),# N
                    "visa_expire": safe_str(vals[14]),# O
                    "shift_start": safe_str(vals[15]),# P
                    "status": "",
                    "extra_json": "",
                })
            processed += 1

        except Exception as e:
            logger.warning("Error processing %s: %s", fp.name, e)
            skipped += 1

    if all_rows:
        with get_conn() as conn:
            conn.execute(
                "DELETE FROM daily_tracking WHERE track_date=?", (track_date,)
            )
            conn.executemany(
                """INSERT INTO daily_tracking
                   (track_date,source_file,region,platform,tab_num,fio,position,
                    section,visa,visa_type,visa_region,visa_expire,shift_start,status)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                [(r["track_date"], r["source_file"], r["region"], r["platform"],
                  r["tab_num"], r["fio"], r["position"], r["section"],
                  r["visa"], r["visa_type"], r["visa_region"], r["visa_expire"],
                  r["shift_start"], r["status"]) for r in all_rows]
            )

    msg = f"Обработано файлов: {processed}, пропущено: {skipped}, строк загружено: {len(all_rows)}"
    log_action("load_daily_tracking", folder_path, len(all_rows), "ok", msg)
    return True, msg, len(all_rows)


def load_ticket_costs(file_paths: List[str]) -> Tuple[bool, str, int]:
    """Загружает реестры по затратам на билеты."""
    from hr_app.backend.database import get_conn
    total_rows = 0
    for fp in file_paths:
        try:
            df = pd.read_excel(fp, header=0, dtype=str)
            df.columns = df.columns.astype(str).str.strip()
            # Generic load - keep all rows
            rows = []
            for _, row in df.iterrows():
                vals = [safe_str(v) for v in row.values]
                rows.append(vals[:12] + [""] * max(0, 12 - len(vals)))
            with get_conn() as conn:
                conn.executemany(
                    """INSERT INTO ticket_costs
                       (source_file,tab_num,fio,route,flight_date,ticket_num,amount,payment,org,department,note)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    [(os.path.basename(fp), *r[:11]) for r in rows]
                )
            total_rows += len(rows)
        except Exception as e:
            logger.warning("Error loading ticket costs from %s: %s", fp, e)
    return True, f"Загружено {total_rows} записей о затратах", total_rows


def export_ticket_orders_excel(orders: List[Dict], output_path: str) -> bool:
    """Экспорт заявок на билеты в Excel (формат как ОП __ Заявка)."""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
        from openpyxl.utils import get_column_letter

        wb = Workbook()
        ws = wb.active
        ws.title = "Заявка"

        header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
        header_font = Font(color="FFFFFF", bold=True, name="Calibri", size=10)
        thin = Side(style="thin")
        border = Border(left=thin, right=thin, top=thin, bottom=thin)

        columns = [
            "№", "Подразделение", "Отдел", "Операция", "Классификация", "Дата заказа",
            "Организация", "Ф.И.О.", "Ф.И.О лат", "Табельный номер", "Гражданство",
            "Дата рождения", "Вид документа", "Серия", "Номер", "Дата выдачи",
            "Дата окончания", "Кем выдан", "Адрес", "Маршрут", "Обоснование",
            "ПС", "АВИА/ЖД", "Дата вылета", "Примечание", "Ответственный",
            "Дата выписки", "Билет", "Сумма", "Оплата", "Причина возврата",
            "Последний перелет", "Телефон", "Трансфер",
        ]
        db_cols = [
            "num", "department", "section_dept", "operation", "classification", "order_date",
            "org", "fio", "fio_lat", "tab_num", "citizenship", "birth_date", "doc_type",
            "doc_series", "doc_num", "doc_issue_date", "doc_expire_date", "doc_issuer",
            "address", "route", "reason", "ps", "transport_type", "flight_date", "note",
            "responsible", "issue_date", "ticket", "amount", "payment", "return_reason",
            "last_flight", "phone", "transfer",
        ]

        for col_idx, col_name in enumerate(columns, 1):
            cell = ws.cell(row=1, column=col_idx, value=col_name)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = border

        for row_idx, order in enumerate(orders, 2):
            for col_idx, db_col in enumerate(db_cols, 1):
                val = order.get(db_col, "")
                if val is None:
                    val = ""
                cell = ws.cell(row=row_idx, column=col_idx, value=val)
                cell.border = border
                cell.font = Font(name="Calibri", size=10)
                cell.alignment = Alignment(vertical="center")

        # Auto width
        for col in ws.columns:
            max_len = max((len(str(c.value or "")) for c in col), default=0)
            ws.column_dimensions[get_column_letter(col[0].column)].width = min(max_len + 2, 45)
        ws.row_dimensions[1].height = 30

        wb.save(output_path)
        return True
    except Exception as e:
        logger.exception("Error exporting to Excel")
        return False
