import os
import tempfile
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, Query, HTTPException
from fastapi.responses import StreamingResponse
from typing import List, Optional
from hr_app.backend.database import get_ticket_orders, save_ticket_orders, get_conn
from hr_app.backend.services.excel_service import export_ticket_orders_excel, safe_str, safe_date

router = APIRouter(prefix="/api/tickets", tags=["tickets"])


@router.get("/orders")
def list_orders(
    department: str = Query(""),
    limit: int = Query(200),
    offset: int = Query(0),
):
    rows, total = get_ticket_orders(department or None, limit, offset)
    return {"rows": rows, "total": total}


@router.post("/orders")
def create_order(order: dict):
    save_ticket_orders([order])
    return {"ok": True}


@router.put("/orders/{order_id}")
def update_order(order_id: int, data: dict):
    fields = [f"{k}=?" for k in data.keys()]
    vals = list(data.values()) + [order_id]
    with get_conn() as conn:
        conn.execute(
            f"UPDATE ticket_orders SET {', '.join(fields)} WHERE id=?", vals
        )
    return {"ok": True}


@router.delete("/orders/{order_id}")
def delete_order(order_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM ticket_orders WHERE id=?", (order_id,))
    return {"ok": True}


@router.get("/orders/export")
def export_orders(department: str = Query("")):
    rows, _ = get_ticket_orders(department or None, 10000, 0)
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        tmp_path = f.name
    export_ticket_orders_excel(rows, tmp_path)

    def file_iter():
        with open(tmp_path, "rb") as f:
            yield from f
        os.unlink(tmp_path)

    dept_label = department.replace(" ", "_") if department else "Все"
    return StreamingResponse(
        file_iter(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="Заявка_{dept_label}.xlsx"'}
    )


@router.post("/upload-pdf")
async def upload_pdf(
    file: UploadFile = File(...),
    department: str = Form(""),
):
    """Обработка PDF билета и извлечение данных."""
    try:
        content = await file.read()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(content)
            tmp_path = f.name

        # Process PDF
        from hr_app.backend.services.pdf_service import extract_ticket_data
        results = extract_ticket_data(tmp_path)
        os.unlink(tmp_path)

        return {"results": results, "filename": file.filename}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/costs")
def list_costs(limit: int = Query(500), offset: int = Query(0)):
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM ticket_costs").fetchone()[0]
        rows = conn.execute(
            "SELECT * FROM ticket_costs ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset)
        ).fetchall()
    return {"rows": [dict(r) for r in rows], "total": total}


@router.get("/costs/summary")
def costs_summary():
    with get_conn() as conn:
        total_amount = conn.execute(
            "SELECT SUM(amount) FROM ticket_costs"
        ).fetchone()[0] or 0
        by_org = conn.execute(
            "SELECT org, SUM(amount) as total, COUNT(*) as cnt "
            "FROM ticket_costs GROUP BY org ORDER BY total DESC"
        ).fetchall()
        by_month = conn.execute(
            "SELECT substr(flight_date,4,7) as month, SUM(amount) as total "
            "FROM ticket_costs WHERE flight_date!='' "
            "GROUP BY month ORDER BY month"
        ).fetchall()
    return {
        "total_amount": total_amount,
        "by_org": [dict(r) for r in by_org],
        "by_month": [dict(r) for r in by_month],
    }


@router.get("/routes")
def get_routes():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT route FROM ticket_orders WHERE route!='' ORDER BY route"
        ).fetchall()
    from hr_app.backend.database import get_setting
    extra = get_setting("routes", "")
    db_routes = [r[0] for r in rows]
    if extra:
        import json
        try:
            db_routes = list(set(db_routes + json.loads(extra)))
        except Exception:
            pass
    return {"routes": sorted(db_routes)}


@router.get("/departments")
def get_departments():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT department FROM ticket_orders WHERE department!='' ORDER BY department"
        ).fetchall()
    return {"departments": [r[0] for r in rows]}
