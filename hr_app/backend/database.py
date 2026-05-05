"""
HR System Database — SQLite через sqlite3
"""
import sqlite3
import json
import logging
import os
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "data" / "hr_system.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=10000")
    return conn


def init_db():
    """Создаёт все таблицы при первом запуске."""
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unique1 TEXT,
            unique2 TEXT,
            tab_num TEXT,
            org TEXT,
            territory TEXT,
            fio TEXT NOT NULL,
            citizenship TEXT,
            birth_date TEXT,
            doc_series TEXT,
            doc_num TEXT,
            position TEXT,
            grade TEXT,
            department TEXT,
            section TEXT,
            section2 TEXT,
            work_schedule TEXT,
            hire_date TEXT,
            fire_date TEXT,
            status TEXT,
            work_start_date TEXT,
            birth_place TEXT,
            doc_issuer TEXT,
            doc_issue_date TEXT,
            address TEXT,
            phone_home TEXT,
            phone_mobile TEXT,
            phone_work TEXT,
            total TEXT,
            region_eju TEXT,
            platform_eju TEXT,
            position_eju TEXT,
            section_eju TEXT,
            section2_eju TEXT,
            visa_eju TEXT,
            visa_type_eju TEXT,
            visa_region_eju TEXT,
            visa_expire_eju TEXT,
            shift_start_eju TEXT,
            status_op TEXT,
            subdivision_blt TEXT,
            classification TEXT,
            dept_category TEXT,
            doc_type TEXT,
            loaded_at TEXT DEFAULT (datetime('now')),
            extra_json TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_emp_fio ON employees(fio);
        CREATE INDEX IF NOT EXISTS idx_emp_tab ON employees(tab_num);
        CREATE INDEX IF NOT EXISTS idx_emp_status_op ON employees(status_op);
        CREATE INDEX IF NOT EXISTS idx_emp_platform ON employees(platform_eju);
        CREATE INDEX IF NOT EXISTS idx_emp_citizenship ON employees(citizenship);
        CREATE INDEX IF NOT EXISTS idx_emp_status ON employees(status);
        CREATE INDEX IF NOT EXISTS idx_emp_org ON employees(org);

        CREATE TABLE IF NOT EXISTS ticket_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            num INTEGER,
            department TEXT,
            section_dept TEXT,
            operation TEXT,
            classification TEXT,
            order_date TEXT,
            org TEXT,
            fio TEXT,
            fio_lat TEXT,
            tab_num TEXT,
            citizenship TEXT,
            birth_date TEXT,
            doc_type TEXT,
            doc_series TEXT,
            doc_num TEXT,
            doc_issue_date TEXT,
            doc_expire_date TEXT,
            doc_issuer TEXT,
            address TEXT,
            route TEXT,
            reason TEXT,
            ps TEXT,
            transport_type TEXT,
            flight_date TEXT,
            note TEXT,
            responsible TEXT,
            issue_date TEXT,
            ticket TEXT,
            amount REAL,
            payment TEXT,
            return_reason TEXT,
            last_flight TEXT,
            phone TEXT,
            transfer TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS ticket_costs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_file TEXT,
            tab_num TEXT,
            fio TEXT,
            route TEXT,
            flight_date TEXT,
            ticket_num TEXT,
            amount REAL,
            payment TEXT,
            org TEXT,
            department TEXT,
            note TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS daily_tracking_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            track_date TEXT NOT NULL,
            filename TEXT NOT NULL,
            source_path TEXT,
            rows_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            loaded_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS daily_tracking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            track_date TEXT NOT NULL,
            source_file TEXT,
            region TEXT,
            platform TEXT,
            tab_num TEXT,
            fio TEXT,
            position TEXT,
            section TEXT,
            visa TEXT,
            visa_type TEXT,
            visa_region TEXT,
            visa_expire TEXT,
            shift_start TEXT,
            status TEXT,
            extra_json TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_dt_date ON daily_tracking(track_date);
        CREATE INDEX IF NOT EXISTS idx_dt_tab ON daily_tracking(tab_num);

        CREATE TABLE IF NOT EXISTS evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER,
            month TEXT,
            tab_num TEXT,
            fio TEXT,
            department TEXT,
            position TEXT,
            category TEXT,
            score REAL,
            note TEXT,
            source_file TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS carnet (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tab_num TEXT,
            fio TEXT,
            department TEXT,
            doc_type TEXT,
            doc_series TEXT,
            doc_num TEXT,
            doc_expire TEXT,
            carnet_type TEXT,
            carnet_num TEXT,
            carnet_expire TEXT,
            note TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS load_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT,
            filename TEXT,
            rows_count INTEGER,
            status TEXT,
            message TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        """)
    logger.info("Database initialized at %s", DB_PATH)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def log_action(action: str, filename: str, rows: int, status: str, message: str = ""):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO load_log (action,filename,rows_count,status,message) VALUES (?,?,?,?,?)",
            (action, filename, rows, status, message)
        )


def get_setting(key: str, default: str = "") -> str:
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM app_settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO app_settings (key,value,updated_at) VALUES (?,?,datetime('now'))",
            (key, value)
        )


# ─── Employees ────────────────────────────────────────────────────────────────

def upsert_employees(records: List[Dict]) -> int:
    """Полная замена базы сотрудников."""
    if not records:
        return 0
    with get_conn() as conn:
        conn.execute("DELETE FROM employees")
        cols = [
            "unique1","unique2","tab_num","org","territory","fio","citizenship",
            "birth_date","doc_series","doc_num","position","grade","department",
            "section","section2","work_schedule","hire_date","fire_date","status",
            "work_start_date","birth_place","doc_issuer","doc_issue_date","address",
            "phone_home","phone_mobile","phone_work","total","region_eju","platform_eju",
            "position_eju","section_eju","section2_eju","visa_eju","visa_type_eju",
            "visa_region_eju","visa_expire_eju","shift_start_eju","status_op",
            "subdivision_blt","classification","dept_category","doc_type","extra_json"
        ]
        placeholders = ",".join(["?"] * len(cols))
        col_str = ",".join(cols)
        rows = []
        for r in records:
            rows.append(tuple(r.get(c, "") or "" for c in cols))
        conn.executemany(
            f"INSERT INTO employees ({col_str}) VALUES ({placeholders})", rows
        )
        return len(rows)


def query_employees(
    status_op: Optional[str] = None,
    platform: Optional[str] = None,
    citizenship: Optional[str] = None,
    status: Optional[str] = None,
    org: Optional[str] = None,
    classification: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 500,
    offset: int = 0
) -> Tuple[List[Dict], int]:
    conditions = []
    params = []

    if status_op and status_op != "ALL":
        if status_op == "ACTIVE":
            conditions.append("status_op = 'Активное ОП'")
        elif status_op == "FINISHED":
            conditions.append("status_op = 'Работы завершены'")

    if platform and platform != "ALL":
        conditions.append("platform_eju = ?")
        params.append(platform)

    if citizenship and citizenship != "ALL":
        conditions.append("citizenship = ?")
        params.append(citizenship)

    if status and status != "ALL":
        conditions.append("status = ?")
        params.append(status)

    if org and org != "ALL":
        conditions.append("org = ?")
        params.append(org)

    if classification and classification != "ALL":
        conditions.append("classification = ?")
        params.append(classification)

    if search:
        conditions.append("(fio LIKE ? OR tab_num LIKE ? OR department LIKE ?)")
        s = f"%{search}%"
        params.extend([s, s, s])

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    with get_conn() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM employees {where}", params
        ).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM employees {where} ORDER BY fio LIMIT ? OFFSET ?",
            params + [limit, offset]
        ).fetchall()

    return [dict(r) for r in rows], total


def get_employee_by_tab(tab_num: str) -> Optional[Dict]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM employees WHERE tab_num=? LIMIT 1", (tab_num,)
        ).fetchone()
    return dict(row) if row else None


def get_employee_by_fio(fio: str) -> Optional[Dict]:
    fio_clean = fio.strip()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM employees WHERE fio=? LIMIT 1", (fio_clean,)
        ).fetchone()
        if not row:
            row = conn.execute(
                "SELECT * FROM employees WHERE fio LIKE ? LIMIT 1", (f"%{fio_clean}%",)
            ).fetchone()
    return dict(row) if row else None


def get_distinct_values(column: str) -> List[str]:
    allowed = {
        "platform_eju","citizenship","status","status_op","org","classification",
        "department","territory","region_eju","work_schedule","subdivision_blt"
    }
    if column not in allowed:
        return []
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT DISTINCT {column} FROM employees WHERE {column}!='' ORDER BY {column}"
        ).fetchall()
    return [r[0] for r in rows if r[0]]


def get_employees_count() -> Dict:
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0]
        active = conn.execute(
            "SELECT COUNT(*) FROM employees WHERE status_op='Активное ОП'"
        ).fetchone()[0]
        finished = conn.execute(
            "SELECT COUNT(*) FROM employees WHERE status_op='Работы завершены'"
        ).fetchone()[0]
        itr = conn.execute(
            "SELECT COUNT(*) FROM employees WHERE classification='ИТР'"
        ).fetchone()[0]
        workers = conn.execute(
            "SELECT COUNT(*) FROM employees WHERE classification='Рабочие'"
        ).fetchone()[0]
    return {
        "total": total, "active_op": active, "finished_op": finished,
        "itr": itr, "workers": workers,
        "foreign": total - conn.execute(
            "SELECT COUNT(*) FROM employees WHERE citizenship IN ('Россия','РФ','РОССИЯ')"
        ).fetchone()[0] if total else 0
    }


# ─── Dashboard aggregates ─────────────────────────────────────────────────────

def get_dashboard_stats(status_op_filter: str = "ALL", platform_filter: str = "ALL") -> Dict:
    conds = []
    params = []
    if status_op_filter == "ACTIVE":
        conds.append("status_op='Активное ОП'")
    elif status_op_filter == "FINISHED":
        conds.append("status_op='Работы завершены'")
    if platform_filter != "ALL":
        conds.append("platform_eju=?")
        params.append(platform_filter)

    where = ("WHERE " + " AND ".join(conds)) if conds else ""

    with get_conn() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM employees {where}", params).fetchone()[0]

        by_citizenship = conn.execute(
            f"SELECT citizenship, COUNT(*) as cnt FROM employees {where} "
            f"GROUP BY citizenship ORDER BY cnt DESC LIMIT 20", params
        ).fetchall()

        by_status = conn.execute(
            f"SELECT status, COUNT(*) as cnt FROM employees {where} "
            f"GROUP BY status ORDER BY cnt DESC", params
        ).fetchall()

        by_classification = conn.execute(
            f"SELECT classification, COUNT(*) as cnt FROM employees {where} "
            f"GROUP BY classification ORDER BY cnt DESC", params
        ).fetchall()

        by_org = conn.execute(
            f"SELECT org, COUNT(*) as cnt FROM employees {where} "
            f"GROUP BY org ORDER BY cnt DESC LIMIT 20", params
        ).fetchall()

        by_platform = conn.execute(
            f"SELECT platform_eju, COUNT(*) as cnt FROM employees {where} "
            f"GROUP BY platform_eju ORDER BY cnt DESC LIMIT 30", params
        ).fetchall()

        by_schedule = conn.execute(
            f"SELECT work_schedule, COUNT(*) as cnt FROM employees {where} "
            f"GROUP BY work_schedule ORDER BY cnt DESC LIMIT 15", params
        ).fetchall()

        hire_cond = "AND hire_date!=''" if where else "WHERE hire_date!=''"
        hire_by_month = conn.execute(
            f"SELECT strftime('%Y-%m', hire_date) as ym, COUNT(*) as cnt "
            f"FROM employees {where} {hire_cond} "
            f"GROUP BY ym ORDER BY ym DESC LIMIT 24", params
        ).fetchall()

        fire_cond = "AND fire_date!=''" if where else "WHERE fire_date!=''"
        fire_by_month = conn.execute(
            f"SELECT strftime('%Y-%m', fire_date) as ym, COUNT(*) as cnt "
            f"FROM employees {where} {fire_cond} "
            f"GROUP BY ym ORDER BY ym DESC LIMIT 24", params
        ).fetchall()

    return {
        "total": total,
        "by_citizenship": [{"label": r[0] or "—", "value": r[1]} for r in by_citizenship],
        "by_status": [{"label": r[0] or "—", "value": r[1]} for r in by_status],
        "by_classification": [{"label": r[0] or "—", "value": r[1]} for r in by_classification],
        "by_org": [{"label": r[0] or "—", "value": r[1]} for r in by_org],
        "by_platform": [{"label": r[0] or "—", "value": r[1]} for r in by_platform],
        "by_schedule": [{"label": r[0] or "—", "value": r[1]} for r in by_schedule],
        "hire_by_month": [{"label": r[0] or "—", "value": r[1]} for r in hire_by_month],
        "fire_by_month": [{"label": r[0] or "—", "value": r[1]} for r in fire_by_month],
    }


# ─── Ticket orders ────────────────────────────────────────────────────────────

def get_ticket_orders(department: str = None, limit: int = 200, offset: int = 0):
    conds = []
    params = []
    if department:
        conds.append("department=?")
        params.append(department)
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    with get_conn() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM ticket_orders {where}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM ticket_orders {where} ORDER BY id DESC LIMIT ? OFFSET ?",
            params + [limit, offset]
        ).fetchall()
    return [dict(r) for r in rows], total


def save_ticket_orders(orders: List[Dict]) -> int:
    if not orders:
        return 0
    cols = [
        "num","department","section_dept","operation","classification","order_date",
        "org","fio","fio_lat","tab_num","citizenship","birth_date","doc_type",
        "doc_series","doc_num","doc_issue_date","doc_expire_date","doc_issuer",
        "address","route","reason","ps","transport_type","flight_date","note",
        "responsible","issue_date","ticket","amount","payment","return_reason",
        "last_flight","phone","transfer"
    ]
    placeholders = ",".join(["?"] * len(cols))
    col_str = ",".join(cols)
    rows = [tuple(o.get(c) for c in cols) for o in orders]
    with get_conn() as conn:
        conn.executemany(f"INSERT INTO ticket_orders ({col_str}) VALUES ({placeholders})", rows)
    return len(rows)


# ─── Reports ─────────────────────────────────────────────────────────────────

def report_headcount_by_org(status_op_filter="ALL", platform_filter="ALL") -> List[Dict]:
    conds, params = _build_filter(status_op_filter, platform_filter)
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT org, classification, COUNT(*) as cnt FROM employees {where} "
            f"GROUP BY org, classification ORDER BY org, classification", params
        ).fetchall()
    return [dict(r) for r in rows]


def report_citizenship(status_op_filter="ALL", platform_filter="ALL") -> List[Dict]:
    conds, params = _build_filter(status_op_filter, platform_filter)
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT citizenship, org, COUNT(*) as cnt FROM employees {where} "
            f"GROUP BY citizenship, org ORDER BY cnt DESC", params
        ).fetchall()
    return [dict(r) for r in rows]


def report_hire_fire_dynamics(status_op_filter="ALL", platform_filter="ALL") -> Dict:
    conds, params = _build_filter(status_op_filter, platform_filter)
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    with get_conn() as conn:
        h_cond = "AND hire_date!=''" if where else "WHERE hire_date!=''"
        hire = conn.execute(
            f"SELECT strftime('%Y-%m', hire_date) as ym, COUNT(*) as cnt "
            f"FROM employees {where} {h_cond} GROUP BY ym ORDER BY ym", params
        ).fetchall()
        f_cond = "AND fire_date!=''" if where else "WHERE fire_date!=''"
        fire = conn.execute(
            f"SELECT strftime('%Y-%m', fire_date) as ym, COUNT(*) as cnt "
            f"FROM employees {where} {f_cond} GROUP BY ym ORDER BY ym", params
        ).fetchall()
    return {
        "hire": [{"label": r[0], "value": r[1]} for r in hire],
        "fire": [{"label": r[0], "value": r[1]} for r in fire],
    }


def report_age_structure(status_op_filter="ALL", platform_filter="ALL") -> List[Dict]:
    conds, params = _build_filter(status_op_filter, platform_filter)
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    with get_conn() as conn:
        rows = conn.execute(
            f"""SELECT
                CASE
                    WHEN CAST(strftime('%Y','now') AS INT) - CAST(substr(birth_date,7,4) AS INT) < 26 THEN '18-25'
                    WHEN CAST(strftime('%Y','now') AS INT) - CAST(substr(birth_date,7,4) AS INT) < 36 THEN '26-35'
                    WHEN CAST(strftime('%Y','now') AS INT) - CAST(substr(birth_date,7,4) AS INT) < 46 THEN '36-45'
                    WHEN CAST(strftime('%Y','now') AS INT) - CAST(substr(birth_date,7,4) AS INT) < 56 THEN '46-55'
                    ELSE '55+'
                END as age_group,
                COUNT(*) as cnt
            FROM employees {where}
            {"AND" if where else "WHERE"} birth_date!='' AND length(birth_date)>=10
            GROUP BY age_group ORDER BY age_group""", params
        ).fetchall()
    return [dict(r) for r in rows]


def report_expiring_docs(days_ahead: int = 30) -> List[Dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT fio, tab_num, citizenship, doc_num, doc_issue_date,
               visa_expire_eju, platform_eju, department
               FROM employees
               WHERE (visa_expire_eju != '' AND
                      date(substr(visa_expire_eju,7,4)||'-'||substr(visa_expire_eju,4,2)||'-'||substr(visa_expire_eju,1,2))
                      <= date('now','+'||?||' days')
                      AND
                      date(substr(visa_expire_eju,7,4)||'-'||substr(visa_expire_eju,4,2)||'-'||substr(visa_expire_eju,1,2))
                      >= date('now'))
               ORDER BY visa_expire_eju LIMIT 500""",
            (str(days_ahead),)
        ).fetchall()
    return [dict(r) for r in rows]


def report_no_phone() -> List[Dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT fio, tab_num, department, platform_eju, citizenship, status
               FROM employees
               WHERE (phone_mobile='' OR phone_mobile IS NULL)
               AND (phone_home='' OR phone_home IS NULL)
               AND (phone_work='' OR phone_work IS NULL)
               ORDER BY fio LIMIT 1000"""
        ).fetchall()
    return [dict(r) for r in rows]


def report_duplicates() -> List[Dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT fio, birth_date, COUNT(*) as cnt, GROUP_CONCAT(tab_num,', ') as tabs
               FROM employees
               GROUP BY fio, birth_date
               HAVING cnt > 1
               ORDER BY cnt DESC LIMIT 500"""
        ).fetchall()
    return [dict(r) for r in rows]


def report_foreign_workers(status_op_filter="ALL", platform_filter="ALL") -> List[Dict]:
    conds, params = _build_filter(status_op_filter, platform_filter)
    conds.append("citizenship NOT IN ('Россия','РФ','РОССИЯ','россия','рф') AND citizenship!=''")
    where = "WHERE " + " AND ".join(conds)
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT fio, tab_num, citizenship, doc_num, doc_issue_date, "
            f"visa_expire_eju, platform_eju, department, status FROM employees {where} "
            f"ORDER BY citizenship, fio LIMIT 2000", params
        ).fetchall()
    return [dict(r) for r in rows]


def _build_filter(status_op_filter, platform_filter):
    conds, params = [], []
    if status_op_filter == "ACTIVE":
        conds.append("status_op='Активное ОП'")
    elif status_op_filter == "FINISHED":
        conds.append("status_op='Работы завершены'")
    if platform_filter and platform_filter != "ALL":
        conds.append("platform_eju=?")
        params.append(platform_filter)
    return conds, params


def get_load_log(limit: int = 50) -> List[Dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM load_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def update_employee_field(emp_id: int, field: str, value: Any) -> bool:
    """Обновляет одно поле сотрудника. Возвращает True при успехе."""
    # whitelist разрешённых полей для обновления
    allowed_fields = {
        "tab_num", "fio", "citizenship", "birth_date", "doc_series", "doc_num",
        "position", "grade", "department", "section", "section2", "work_schedule",
        "hire_date", "fire_date", "status", "work_start_date", "birth_place",
        "doc_issuer", "doc_issue_date", "address", "phone_home", "phone_mobile",
        "phone_work", "total", "region_eju", "platform_eju", "position_eju",
        "section_eju", "section2_eju", "visa_eju", "visa_type_eju", "visa_region_eju",
        "visa_expire_eju", "shift_start_eju", "status_op", "subdivision_blt",
        "classification", "dept_category", "doc_type", "org", "territory"
    }
    
    if field not in allowed_fields and field != "id":
        logger.warning(f"Попытка обновления недопустимого поля: {field}")
        return False
    
    try:
        with get_conn() as conn:
            conn.execute(
                f"UPDATE employees SET {field}=? WHERE id=?",
                (value if value is not None else "", emp_id)
            )
        return True
    except Exception as e:
        logger.error(f"Ошибка обновления поля {field} для сотрудника {emp_id}: {e}")
        return False
