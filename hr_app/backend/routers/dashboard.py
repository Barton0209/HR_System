from fastapi import APIRouter, Query
from hr_app.backend.database import (
    get_dashboard_stats, get_employees_count, get_distinct_values,
    query_employees
)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats")
def dashboard_stats(
    status_op: str = Query("ALL"),
    platform: str = Query("ALL"),
):
    stats = get_dashboard_stats(status_op, platform)
    counts = get_employees_count()
    return {"stats": stats, "counts": counts}


@router.get("/filters")
def dashboard_filters():
    return {
        "platforms": ["ALL"] + get_distinct_values("platform_eju"),
        "citizenships": ["ALL"] + get_distinct_values("citizenship"),
        "statuses": ["ALL"] + get_distinct_values("status"),
        "orgs": ["ALL"] + get_distinct_values("org"),
        "classifications": ["ALL"] + get_distinct_values("classification"),
        "schedules": ["ALL"] + get_distinct_values("work_schedule"),
        "departments": ["ALL"] + get_distinct_values("department"),
    }
