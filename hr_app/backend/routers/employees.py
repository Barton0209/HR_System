from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from hr_app.backend.database import (
    query_employees, get_employee_by_tab, get_employee_by_fio, get_distinct_values
)

router = APIRouter(prefix="/api/employees", tags=["employees"])


@router.get("")
def list_employees(
    status_op: str = Query("ALL"),
    platform: str = Query("ALL"),
    citizenship: str = Query("ALL"),
    status: str = Query("ALL"),
    org: str = Query("ALL"),
    classification: str = Query("ALL"),
    search: str = Query(""),
    limit: int = Query(100, le=1000),
    offset: int = Query(0),
):
    rows, total = query_employees(
        status_op=status_op,
        platform=platform,
        citizenship=citizenship,
        status=status,
        org=org,
        classification=classification,
        search=search or None,
        limit=limit,
        offset=offset,
    )
    return {"rows": rows, "total": total, "limit": limit, "offset": offset}


@router.get("/by-tab/{tab_num}")
def get_by_tab(tab_num: str):
    emp = get_employee_by_tab(tab_num)
    if not emp:
        raise HTTPException(404, "Сотрудник не найден")
    return emp


@router.get("/by-fio")
def get_by_fio(fio: str = Query(...)):
    emp = get_employee_by_fio(fio)
    if not emp:
        raise HTTPException(404, "Сотрудник не найден")
    return emp


@router.get("/distinct/{column}")
def distinct_values(column: str):
    return get_distinct_values(column)
