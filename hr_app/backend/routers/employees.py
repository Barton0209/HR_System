"""
Employees Router — FastAPI с Pydantic валидацией
"""
import logging
from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field

from hr_app.backend.database import (
    query_employees, get_employee_by_tab, get_employee_by_fio, get_distinct_values, update_employee_field
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/employees", tags=["employees"])


# ─── Pydantic Models ────────────────────────────────────────────────────────────

class EmployeeResponse(BaseModel):
    """Модель ответа для сотрудника."""
    id: int
    tab_num: Optional[str] = None
    fio: str
    citizenship: Optional[str] = None
    birth_date: Optional[str] = None
    position: Optional[str] = None
    department: Optional[str] = None
    platform_eju: Optional[str] = None
    status: Optional[str] = None
    status_op: Optional[str] = None
    classification: Optional[str] = None
    work_schedule: Optional[str] = None
    hire_date: Optional[str] = None
    fire_date: Optional[str] = None
    phone_mobile: Optional[str] = None
    org: Optional[str] = None
    
    class Config:
        from_attributes = True


class EmployeeChange(BaseModel):
    """Модель изменения сотрудника."""
    id: int
    field: str
    newValue: Any


class BatchUpdateRequest(BaseModel):
    """Запрос на пакетное обновление."""
    changes: List[EmployeeChange]


class EmployeesListResponse(BaseModel):
    """Модель ответа для списка сотрудников."""
    rows: List[Any]
    total: int
    limit: int
    offset: int


class DistinctValuesResponse(BaseModel):
    """Модель ответа для уникальных значений."""
    values: List[str]


class BatchUpdateResponse(BaseModel):
    """Ответ на пакетное обновление."""
    updated: int
    failed: int


# ─── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("", response_model=EmployeesListResponse)
def list_employees(
    status_op: str = Query("ALL", description="Фильтр по статусу ОП"),
    platform: str = Query("ALL", description="Фильтр по площадке"),
    citizenship: str = Query("ALL", description="Фильтр по гражданству"),
    status: str = Query("ALL", description="Фильтр по статусу"),
    org: str = Query("ALL", description="Фильтр по организации"),
    classification: str = Query("ALL", description="Фильтр по классификации"),
    search: str = Query("", description="Поиск по ФИО, табному номеру"),
    limit: int = Query(100, le=1000, description="Лимит записей"),
    offset: int = Query(0, ge=0, description="Смещение"),
):
    """Получить список сотрудников с фильтрацией и пагинацией."""
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


@router.get("/by-tab/{tab_num}", response_model=EmployeeResponse)
def get_by_tab(tab_num: str):
    """Получить сотрудника по табельному номеру."""
    emp = get_employee_by_tab(tab_num)
    if not emp:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    return emp


@router.get("/by-fio", response_model=EmployeeResponse)
def get_by_fio(fio: str = Query(..., description="ФИО сотрудника")):
    """Получить сотрудника по ФИО."""
    emp = get_employee_by_fio(fio)
    if not emp:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    return emp


@router.get("/distinct/{column}", response_model=DistinctValuesResponse)
def distinct_values(column: str):
    """Получить уникальные значения для указанного поля."""
    values = get_distinct_values(column)
    return {"values": values}


@router.post("/batch-update", response_model=BatchUpdateResponse)
async def batch_update(request: BatchUpdateRequest):
    """Пакетное обновление сотрудников из Handsontable."""
    updated = 0
    failed = 0
    
    for change in request.changes:
        try:
            success = update_employee_field(change.id, change.field, change.newValue)
            if success:
                updated += 1
            else:
                failed += 1
        except Exception as e:
            failed += 1
            logger.error(f"Ошибка обновления сотрудника {change.id}: {e}")
    
    return {"updated": updated, "failed": failed}
