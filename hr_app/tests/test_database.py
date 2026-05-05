"""
Tests for HR System Backend
Запуск: pytest hr_app/tests/ -v
"""
import pytest
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from database import (
    get_conn, init_db, upsert_employees, query_employees, 
    get_employee_by_tab, get_employee_by_fio, get_distinct_values,
    get_employees_count, log_action, get_setting, set_setting
)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    """Инициализация БД перед тестами."""
    init_db()
    yield
    # Cleanup можно добавить при необходимости


@pytest.fixture
def sample_employee():
    return {
        "unique1": "TEST001",
        "unique2": "TEST001",
        "tab_num": "12345",
        "org": "ООО Тест",
        "territory": "Москва",
        "fio": "Иванов Иван Иванович",
        "citizenship": "Россия",
        "birth_date": "1990-01-15",
        "doc_series": "4500",
        "doc_num": "123456",
        "position": "Инженер",
        "grade": "5",
        "department": "Отдел разработки",
        "section": "Участок 1",
        "section2": "",
        "work_schedule": "5/2",
        "hire_date": "2024-01-10",
        "fire_date": "",
        "status": "Действует",
        "work_start_date": "2024-01-10",
        "birth_place": "Москва",
        "doc_issuer": "МВД",
        "doc_issue_date": "2020-01-01",
        "address": "ул. Тестовая, д.1",
        "phone_home": "",
        "phone_mobile": "+79991234567",
        "phone_work": "",
        "total": "10",
        "region_eju": "Москва",
        "platform_eju": "Площадка А",
        "position_eju": "Инженер",
        "section_eju": "Участок 1",
        "section2_eju": "",
        "visa_eju": "",
        "visa_type_eju": "",
        "visa_region_eju": "",
        "visa_expire_eju": "",
        "shift_start_eju": "",
        "status_op": "Активное ОП",
        "subdivision_blt": "",
        "classification": "ИТР",
        "dept_category": "",
        "doc_type": "Паспорт РФ",
        "extra_json": "{}"
    }


class TestDatabaseConnection:
    def test_get_conn(self):
        conn = get_conn()
        assert conn is not None
        cursor = conn.execute("SELECT 1")
        assert cursor.fetchone()[0] == 1
        conn.close()

    def test_wal_mode(self):
        conn = get_conn()
        result = conn.execute("PRAGMA journal_mode").fetchone()
        assert result[0] == "wal"
        conn.close()


class TestEmployeesCRUD:
    def test_upsert_and_query(self, sample_employee):
        # Insert
        count = upsert_employees([sample_employee])
        assert count == 1
        
        # Query all
        rows, total = query_employees(limit=10, offset=0)
        assert total >= 1
        assert any(r["tab_num"] == "12345" for r in rows)
        
        # Query by tab_num filter (search)
        rows, total = query_employees(search="12345", limit=10, offset=0)
        assert total == 1
        assert rows[0]["fio"] == "Иванов Иван Иванович"

    def test_get_employee_by_tab(self, sample_employee):
        emp = get_employee_by_tab("12345")
        assert emp is not None
        assert emp["fio"] == "Иванов Иван Иванович"
        assert emp["citizenship"] == "Россия"

    def test_get_employee_by_fio(self, sample_employee):
        emp = get_employee_by_fio("Иванов Иван Иванович")
        assert emp is not None
        assert emp["tab_num"] == "12345"

    def test_get_employee_not_found(self):
        emp = get_employee_by_tab("NONEXISTENT")
        assert emp is None
        
        emp = get_employee_by_fio("Неexistent Person")
        assert emp is None

    def test_query_filters(self, sample_employee):
        # Filter by status_op
        rows, total = query_employees(status_op="ACTIVE", limit=10, offset=0)
        assert total >= 1
        
        # Filter by platform
        rows, total = query_employees(platform="Площадка А", limit=10, offset=0)
        assert total >= 1
        
        # Filter by citizenship
        rows, total = query_employees(citizenship="Россия", limit=10, offset=0)
        assert total >= 1

    def test_distinct_values(self):
        values = get_distinct_values("platform_eju")
        assert isinstance(values, list)
        assert "Площадка А" in values
        
        values = get_distinct_values("citizenship")
        assert isinstance(values, list)
        assert "Россия" in values

    def test_invalid_column_distinct(self):
        values = get_distinct_values("invalid_column")
        assert values == []

    def test_employees_count(self):
        stats = get_employees_count()
        assert "total" in stats
        assert stats["total"] >= 1
        assert "active_op" in stats
        assert "itr" in stats
        assert "workers" in stats


class TestSettings:
    def test_set_and_get_setting(self):
        set_setting("test_key", "test_value")
        value = get_setting("test_key")
        assert value == "test_value"
        
        # Default value
        value = get_setting("nonexistent_key", "default")
        assert value == "default"


class TestLogging:
    def test_log_action(self):
        log_action(
            action="TEST_INSERT",
            filename="test_file.xlsx",
            rows=100,
            status="success",
            message="Test log entry"
        )
        # Verify log entry exists
        conn = get_conn()
        row = conn.execute(
            "SELECT * FROM load_log WHERE action='TEST_INSERT' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        assert row is not None
        assert row["filename"] == "test_file.xlsx"
        assert row["rows_count"] == 100
        assert row["status"] == "success"
        conn.close()


class TestPagination:
    def test_pagination(self, sample_employee):
        # Insert multiple records
        employees = []
        for i in range(50):
            emp = sample_employee.copy()
            emp["tab_num"] = f"TAB{i:05d}"
            emp["fio"] = f"Фамилия{i:03d} Имя{i:03d} Отчество{i:03d}"
            employees.append(emp)
        
        count = upsert_employees(employees)
        assert count == 50
        
        # Test pagination
        rows1, total1 = query_employees(limit=20, offset=0)
        rows2, total2 = query_employees(limit=20, offset=20)
        rows3, total3 = query_employees(limit=20, offset=40)
        
        assert len(rows1) == 20
        assert len(rows2) == 20
        assert len(rows3) == 10
        assert total1 == total2 == total3 == 50


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
