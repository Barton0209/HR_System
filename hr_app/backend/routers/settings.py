import os
import json
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from hr_app.backend.database import get_setting, set_setting, get_load_log, get_conn
from hr_app.backend.services.excel_service import load_main_base, load_ticket_costs

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
def get_all_settings():
    with get_conn() as conn:
        rows = conn.execute("SELECT key, value, updated_at FROM app_settings").fetchall()
    return {"settings": [dict(r) for r in rows]}


@router.post("/set")
def set_setting_endpoint(key: str = Form(...), value: str = Form(...)):
    set_setting(key, value)
    return {"ok": True}


@router.post("/upload-main-base")
async def upload_main_base(file: UploadFile = File(...)):
    """Загрузка БАЗА.xlsx"""
    content = await file.read()
    tmp_path = Path("data") / "uploads" / file.filename
    tmp_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path.write_bytes(content)

    ok, msg, count = load_main_base(str(tmp_path))
    if ok:
        set_setting("main_base_path", str(tmp_path))
        set_setting("main_base_name", file.filename)
        set_setting("main_base_rows", str(count))
    return {"ok": ok, "message": msg, "count": count}


@router.post("/upload-ticket-costs")
async def upload_ticket_costs(files: list[UploadFile] = File(...)):
    """Загрузка реестров по затратам на билеты."""
    saved_paths = []
    for f in files:
        content = await f.read()
        tmp_path = Path("data") / "uploads" / f.filename
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_bytes(content)
        saved_paths.append(str(tmp_path))

    ok, msg, count = load_ticket_costs(saved_paths)
    return {"ok": ok, "message": msg, "count": count}


@router.post("/upload-routes")
async def upload_routes(file: UploadFile = File(...)):
    """Загрузка МАРШРУТ.xlsx"""
    import pandas as pd
    content = await file.read()
    tmp_path = Path("data") / "uploads" / file.filename
    tmp_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path.write_bytes(content)

    try:
        df = pd.read_excel(str(tmp_path), dtype=str)
        routes = df.iloc[:, 0].dropna().astype(str).tolist()
        routes = [r.strip() for r in routes if r.strip() and r.strip() != "nan"]
        set_setting("routes", json.dumps(routes, ensure_ascii=False))
        return {"ok": True, "count": len(routes), "routes": routes[:20]}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/reload-main-base")
def reload_main_base():
    path = get_setting("main_base_path")
    if not path or not Path(path).exists():
        raise HTTPException(404, "Файл базы не найден. Загрузите через форму.")
    ok, msg, count = load_main_base(path)
    return {"ok": ok, "message": msg, "count": count}


@router.get("/load-log")
def load_log(limit: int = 50):
    return {"log": get_load_log(limit)}


@router.get("/db-info")
def db_info():
    from hr_app.backend.database import get_employees_count, DB_PATH
    counts = get_employees_count()
    return {
        "db_path": str(DB_PATH),
        "db_size_mb": round(os.path.getsize(str(DB_PATH)) / 1024 / 1024, 2) if DB_PATH.exists() else 0,
        "employees": counts,
        "main_base_name": get_setting("main_base_name", "не загружена"),
        "main_base_rows": get_setting("main_base_rows", "0"),
    }
