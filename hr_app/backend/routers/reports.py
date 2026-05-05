import io
from fastapi import APIRouter, Query, Response
from fastapi.responses import StreamingResponse
from hr_app.backend.database import (
    report_headcount_by_org, report_citizenship, report_hire_fire_dynamics,
    report_age_structure, report_expiring_docs, report_no_phone,
    report_duplicates, report_foreign_workers, query_employees,
    get_distinct_values
)

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/headcount")
def headcount(
    status_op: str = Query("ALL"),
    platform: str = Query("ALL"),
):
    rows = report_headcount_by_org(status_op, platform)
    return {"rows": rows}


@router.get("/citizenship")
def citizenship(
    status_op: str = Query("ALL"),
    platform: str = Query("ALL"),
):
    rows = report_citizenship(status_op, platform)
    return {"rows": rows}


@router.get("/dynamics")
def dynamics(
    status_op: str = Query("ALL"),
    platform: str = Query("ALL"),
):
    return report_hire_fire_dynamics(status_op, platform)


@router.get("/age-structure")
def age_structure(
    status_op: str = Query("ALL"),
    platform: str = Query("ALL"),
):
    rows = report_age_structure(status_op, platform)
    return {"rows": rows}


@router.get("/expiring-docs")
def expiring_docs(days: int = Query(30)):
    rows = report_expiring_docs(days)
    return {"rows": rows, "total": len(rows)}


@router.get("/no-phone")
def no_phone():
    rows = report_no_phone()
    return {"rows": rows, "total": len(rows)}


@router.get("/duplicates")
def duplicates():
    rows = report_duplicates()
    return {"rows": rows, "total": len(rows)}


@router.get("/foreign-workers")
def foreign_workers(
    status_op: str = Query("ALL"),
    platform: str = Query("ALL"),
):
    rows = report_foreign_workers(status_op, platform)
    return {"rows": rows, "total": len(rows)}


@router.get("/by-schedule")
def by_schedule(
    status_op: str = Query("ALL"),
    platform: str = Query("ALL"),
):
    from hr_app.backend.database import _build_filter, get_conn
    conds, params = _build_filter(status_op, platform)
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT work_schedule, COUNT(*) as cnt FROM employees {where} "
            f"GROUP BY work_schedule ORDER BY cnt DESC", params
        ).fetchall()
    return {"rows": [dict(r) for r in rows]}


@router.get("/by-position")
def by_position(
    status_op: str = Query("ALL"),
    platform: str = Query("ALL"),
    limit: int = Query(20),
):
    from hr_app.backend.database import _build_filter, get_conn
    conds, params = _build_filter(status_op, platform)
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT position, COUNT(*) as cnt FROM employees {where} "
            f"GROUP BY position ORDER BY cnt DESC LIMIT ?", params + [limit]
        ).fetchall()
    return {"rows": [dict(r) for r in rows]}


@router.get("/by-department")
def by_department(
    status_op: str = Query("ALL"),
    platform: str = Query("ALL"),
):
    from hr_app.backend.database import _build_filter, get_conn
    conds, params = _build_filter(status_op, platform)
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT department, org, classification, COUNT(*) as cnt FROM employees {where} "
            f"GROUP BY department, org, classification ORDER BY cnt DESC LIMIT 300", params
        ).fetchall()
    return {"rows": [dict(r) for r in rows]}


@router.get("/org-tree")
def org_tree(
    status_op: str = Query("ALL"),
    platform: str = Query("ALL"),
):
    """Иерархия: Организация → Подразделение → Должность → Кол-во"""
    from hr_app.backend.database import _build_filter, get_conn
    conds, params = _build_filter(status_op, platform)
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT org, department, position, COUNT(*) as cnt FROM employees {where} "
            f"GROUP BY org, department, position ORDER BY org, department, cnt DESC", params
        ).fetchall()

    tree = {}
    for r in rows:
        org = r["org"] or "—"
        dept = r["department"] or "—"
        pos = r["position"] or "—"
        cnt = r["cnt"]
        if org not in tree:
            tree[org] = {"name": org, "count": 0, "children": {}}
        tree[org]["count"] += cnt
        if dept not in tree[org]["children"]:
            tree[org]["children"][dept] = {"name": dept, "count": 0, "children": {}}
        tree[org]["children"][dept]["count"] += cnt
        tree[org]["children"][dept]["children"][pos] = cnt

    return {"tree": tree}


@router.get("/export-excel/{report_type}")
async def export_excel(report_type: str, status_op: str = "ALL", platform: str = "ALL"):
    """Экспорт любого отчёта в Excel."""
    import pandas as pd
    from io import BytesIO

    data_map = {
        "headcount": lambda: report_headcount_by_org(status_op, platform),
        "citizenship": lambda: report_citizenship(status_op, platform),
        "age": lambda: report_age_structure(status_op, platform),
        "expiring": lambda: report_expiring_docs(30),
        "no-phone": lambda: report_no_phone(),
        "duplicates": lambda: report_duplicates(),
        "foreign": lambda: report_foreign_workers(status_op, platform),
    }

    if report_type not in data_map:
        return Response(status_code=404)

    rows = data_map[report_type]()
    df = pd.DataFrame(rows)

    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Отчёт")
    buf.seek(0)

    filename = f"report_{report_type}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
