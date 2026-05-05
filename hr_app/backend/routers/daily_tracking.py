import os
import shutil
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, Query, UploadFile, File, Form, HTTPException
from hr_app.backend.database import get_conn
from hr_app.backend.services.excel_service import load_daily_tracking_files

router = APIRouter(prefix="/api/daily-tracking", tags=["daily_tracking"])

DOWNLOAD_DIR = Path("data/EJU/Download")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.get("/dates")
def available_dates():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT track_date, COUNT(*) as cnt "
            "FROM daily_tracking GROUP BY track_date ORDER BY track_date DESC LIMIT 60"
        ).fetchall()
    return {"dates": [{"date": r[0], "count": r[1]} for r in rows]}


@router.get("/data")
def get_tracking_data(
    track_date: str = Query(...),
    platform: str = Query("ALL"),
    search: str = Query(""),
    limit: int = Query(200),
    offset: int = Query(0),
):
    conds = ["track_date=?"]
    params = [track_date]
    if platform != "ALL":
        conds.append("platform=?")
        params.append(platform)
    if search:
        conds.append("(fio LIKE ? OR tab_num LIKE ?)")
        s = f"%{search}%"
        params.extend([s, s])

    where = "WHERE " + " AND ".join(conds)
    with get_conn() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM daily_tracking {where}", params
        ).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM daily_tracking {where} ORDER BY platform, fio LIMIT ? OFFSET ?",
            params + [limit, offset]
        ).fetchall()
    return {"rows": [dict(r) for r in rows], "total": total}


@router.post("/upload-folder")
async def upload_tracking_files(
    track_date: str = Form(...),
    files: list[UploadFile] = File(...),
):
    """Загрузка файлов ежедневного учёта через браузер."""
    date_dir = DOWNLOAD_DIR / track_date
    date_dir.mkdir(parents=True, exist_ok=True)

    saved = []
    for f in files:
        dst = date_dir / f.filename
        content = await f.read()
        dst.write_bytes(content)
        saved.append(f.filename)

    ok, msg, count = load_daily_tracking_files(str(date_dir), track_date)
    return {"ok": ok, "message": msg, "rows": count, "files": saved}


@router.post("/process-folder")
def process_local_folder(
    folder_path: str = Form(...),
    track_date: str = Form(...),
):
    """Обработка локальной папки с файлами ЕЖУ."""
    ok, msg, count = load_daily_tracking_files(folder_path, track_date)
    return {"ok": ok, "message": msg, "rows": count}


@router.get("/platforms")
def tracking_platforms(track_date: str = Query(...)):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT platform, COUNT(*) as cnt FROM daily_tracking "
            "WHERE track_date=? GROUP BY platform ORDER BY cnt DESC",
            (track_date,)
        ).fetchall()
    return {"platforms": ["ALL"] + [r[0] for r in rows if r[0]]}


@router.get("/summary")
def tracking_summary(track_date: str = Query(...)):
    with get_conn() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM daily_tracking WHERE track_date=?", (track_date,)
        ).fetchone()[0]
        by_platform = conn.execute(
            "SELECT platform, COUNT(*) as cnt FROM daily_tracking "
            "WHERE track_date=? GROUP BY platform ORDER BY cnt DESC",
            (track_date,)
        ).fetchall()
        by_source = conn.execute(
            "SELECT source_file, COUNT(*) as cnt FROM daily_tracking "
            "WHERE track_date=? GROUP BY source_file ORDER BY cnt DESC",
            (track_date,)
        ).fetchall()
    return {
        "total": total,
        "by_platform": [dict(r) for r in by_platform],
        "by_source": [dict(r) for r in by_source],
    }
