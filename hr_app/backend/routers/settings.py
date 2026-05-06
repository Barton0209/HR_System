import os
import json
import re
import logging
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from hr_app.backend.database import get_setting, set_setting, get_load_log, get_conn
from hr_app.backend.services.excel_service import (
    load_main_base, load_ticket_costs, load_total_experience,
    load_password_access, load_departments, load_areas, load_positions,
    generate_total_experience_report, generate_ticket_costs_report
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])


def sanitize_filename(filename: str) -> str:
    """Санитизация имени файла для предотвращения Path Traversal."""
    # Удаляем любые пути
    filename = Path(filename).name
    
    # Разрешаем только буквы, цифры, дефис, подчёркивание и точку
    safe_name = re.sub(r'[^a-zA-Z0-9_\-.а-яА-ЯёЁ\s]', '_', filename)
    
    # Удаляем множественные пробелы
    safe_name = re.sub(r'\s+', ' ', safe_name).strip()
    
    # Проверяем расширение
    allowed_extensions = {'.xlsx', '.xls', '.xlsm', '.xlsb'}
    ext = Path(safe_name).suffix.lower()
    if ext not in allowed_extensions:
        raise HTTPException(400, f"Недопустимое расширение файла: {ext}")
    
    return safe_name


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
    try:
        safe_name = sanitize_filename(file.filename)
        content = await file.read()
        
        # Проверка размера файла (макс 100MB)
        if len(content) > 100 * 1024 * 1024:
            raise HTTPException(400, "Файл слишком большой (макс. 100MB)")
        
        tmp_path = Path("data") / "uploads" / safe_name
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_bytes(content)

        ok, msg, count = load_main_base(str(tmp_path))
        if ok:
            set_setting("main_base_path", str(tmp_path))
            set_setting("main_base_name", safe_name)
            set_setting("main_base_rows", str(count))
        return {"ok": ok, "message": msg, "count": count}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Ошибка загрузки основной базы")
        raise HTTPException(500, f"Ошибка загрузки: {str(e)}")


@router.post("/upload-ticket-costs")
async def upload_ticket_costs(files: list[UploadFile] = File(...)):
    """Загрузка реестров по затратам на билеты."""
    try:
        saved_paths = []
        for f in files:
            safe_name = sanitize_filename(f.filename)
            content = await f.read()
            
            # Проверка размера файла (макс 50MB)
            if len(content) > 50 * 1024 * 1024:
                raise HTTPException(400, f"Файл {safe_name} слишком большой (макс. 50MB)")
            
            tmp_path = Path("data") / "uploads" / safe_name
            tmp_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path.write_bytes(content)
            saved_paths.append(str(tmp_path))

        ok, msg, count = load_ticket_costs(saved_paths)
        return {"ok": ok, "message": msg, "count": count}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Ошибка загрузки реестров билетов")
        raise HTTPException(500, f"Ошибка загрузки: {str(e)}")


@router.post("/upload-routes")
async def upload_routes(file: UploadFile = File(...)):
    """Загрузка МАРШРУТ.xlsx"""
    import pandas as pd
    try:
        safe_name = sanitize_filename(file.filename)
        content = await file.read()
        
        if len(content) > 50 * 1024 * 1024:
            raise HTTPException(400, "Файл слишком большой (макс. 50MB)")
        
        tmp_path = Path("data") / "uploads" / safe_name
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_bytes(content)

        df = pd.read_excel(str(tmp_path), dtype=str)
        routes = df.iloc[:, 0].dropna().astype(str).tolist()
        routes = [r.strip() for r in routes if r.strip() and r.strip() != "nan"]
        set_setting("routes", json.dumps(routes, ensure_ascii=False))
        return {"ok": True, "count": len(routes), "routes": routes[:20]}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Ошибка загрузки маршрутов")
        raise HTTPException(500, f"Ошибка загрузки: {str(e)}")


@router.post("/upload-total-experience")
async def upload_total_experience(file: UploadFile = File(...)):
    """Загрузка ОБЩИЙ_СТАЖ.xlsx - отдельный расчет общего стажа"""
    try:
        safe_name = sanitize_filename(file.filename)
        content = await file.read()
        
        if len(content) > 100 * 1024 * 1024:
            raise HTTPException(400, "Файл слишком большой (макс. 100MB)")
        
        tmp_path = Path("data") / "uploads" / safe_name
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_bytes(content)

        ok, msg, count = load_total_experience(str(tmp_path))
        if ok:
            set_setting("total_experience_path", str(tmp_path))
            set_setting("total_experience_name", safe_name)
            set_setting("total_experience_rows", str(count))
        return {"ok": ok, "message": msg, "count": count}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Ошибка загрузки стажа")
        raise HTTPException(500, f"Ошибка загрузки: {str(e)}")


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


# ============================================================================
# ЗАГРУЗКА СПРАВОЧНИКОВ И ПАРОЛЕЙ ДОСТУПА
# ============================================================================

@router.post("/upload-password-access")
async def upload_password_access(file: UploadFile = File(...)):
    """Загрузка ПАРОЛЬ_ДОСТУП.xlsx - лист ПАРОЛЬ_ДОСТУП
    Колонки: Логин, Пароль, ДОСТУП (Площадка_ЕЖУ), ФИО, Email, Должность, Отдел, Доступ к Карнет
    """
    try:
        safe_name = sanitize_filename(file.filename)
        content = await file.read()
        
        if len(content) > 50 * 1024 * 1024:
            raise HTTPException(400, "Файл слишком большой (макс. 50MB)")
        
        tmp_path = Path("data") / "uploads" / safe_name
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_bytes(content)
        
        ok, msg, count = load_password_access(str(tmp_path))
        if ok:
            set_setting("password_access_path", str(tmp_path))
            set_setting("password_access_name", safe_name)
            set_setting("password_access_count", str(count))
        return {"ok": ok, "message": msg, "count": count}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Ошибка загрузки паролей доступа")
        raise HTTPException(500, f"Ошибка загрузки: {str(e)}")


@router.post("/upload-departments")
async def upload_departments(file: UploadFile = File(...)):
    """Загрузка Подразделение_Отдел_Участок.xlsx"""
    try:
        safe_name = sanitize_filename(file.filename)
        content = await file.read()
        
        if len(content) > 50 * 1024 * 1024:
            raise HTTPException(400, "Файл слишком большой (макс. 50MB)")
        
        tmp_path = Path("data") / "uploads" / safe_name
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_bytes(content)
        
        ok, msg, count = load_departments(str(tmp_path))
        if ok:
            set_setting("departments_path", str(tmp_path))
            set_setting("departments_name", safe_name)
        return {"ok": ok, "message": msg, "count": count}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Ошибка загрузки подразделений")
        raise HTTPException(500, f"Ошибка загрузки: {str(e)}")


@router.post("/upload-areas")
async def upload_areas(file: UploadFile = File(...)):
    """Загрузка Терр_ПЛОЩ_ПОДР_СтатусОП_Регион.xlsx"""
    try:
        safe_name = sanitize_filename(file.filename)
        content = await file.read()
        
        if len(content) > 50 * 1024 * 1024:
            raise HTTPException(400, "Файл слишком большой (макс. 50MB)")
        
        tmp_path = Path("data") / "uploads" / safe_name
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_bytes(content)
        
        ok, msg, count = load_areas(str(tmp_path))
        if ok:
            set_setting("areas_path", str(tmp_path))
            set_setting("areas_name", safe_name)
        return {"ok": ok, "message": msg, "count": count}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Ошибка загрузки территорий")
        raise HTTPException(500, f"Ошибка загрузки: {str(e)}")


@router.post("/upload-positions")
async def upload_positions(file: UploadFile = File(...)):
    """Загрузка Должность, Классификация.xlsx"""
    try:
        safe_name = sanitize_filename(file.filename)
        content = await file.read()
        
        if len(content) > 50 * 1024 * 1024:
            raise HTTPException(400, "Файл слишком большой (макс. 50MB)")
        
        tmp_path = Path("data") / "uploads" / safe_name
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_bytes(content)
        
        ok, msg, count = load_positions(str(tmp_path))
        if ok:
            set_setting("positions_path", str(tmp_path))
            set_setting("positions_name", safe_name)
        return {"ok": ok, "message": msg, "count": count}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Ошибка загрузки должностей")
        raise HTTPException(500, f"Ошибка загрузки: {str(e)}")


@router.post("/generate-total-experience-report")
async def generate_total_experience_report_endpoint():
    """Генерация отчета ОБЩИЙ_СТАЖ.xlsx из основной базы"""
    try:
        output_path = Path("data/reports") / "ОБЩИЙ_СТАЖ.xlsx"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        ok, msg, count = generate_total_experience_report(str(output_path))
        if ok:
            return {"ok": True, "message": msg, "count": count, "path": str(output_path)}
        return {"ok": False, "message": msg}
    except Exception as e:
        logger.exception("Ошибка генерации отчета стажа")
        raise HTTPException(500, f"Ошибка генерации: {str(e)}")


@router.post("/generate-ticket-costs-report")
async def generate_ticket_costs_report_endpoint():
    """Генерация Реестр_по_затратам_на_билеты.xlsx из загруженных реестров"""
    try:
        output_path = Path("data/reports") / "Реестр_по_затратам_на_билеты.xlsx"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        ok, msg, count = generate_ticket_costs_report(str(output_path))
        if ok:
            return {"ok": True, "message": msg, "count": count, "path": str(output_path)}
        return {"ok": False, "message": msg}
    except Exception as e:
        logger.exception("Ошибка генерации отчета билетов")
        raise HTTPException(500, f"Ошибка генерации: {str(e)}")


@router.get("/download-report/{filename}")
async def download_report(filename: str):
    """Скачивание сгенерированного отчета"""
    from fastapi.responses import FileResponse
    
    report_path = Path("data/reports") / filename
    if not report_path.exists():
        raise HTTPException(404, "Отчет не найден")
    
    return FileResponse(
        str(report_path),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=filename
    )
