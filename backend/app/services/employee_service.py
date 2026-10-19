import csv
import io
from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from app.core.enums import EmployeeStatus
from app.core.errors import ConflictError, NotFoundError, UnprocessableError
from app.core.reference import currency_for
from app.models import Employee, SalaryChange, User
from app.schemas.employee import EmployeeCreate, EmployeeUpdate

SORTABLE_FIELDS = (
    "id",
    "employee_code",
    "first_name",
    "last_name",
    "job_title",
    "department",
    "country_code",
    "salary",
    "hire_date",
    "status",
)

CSV_COLUMNS = (
    "employee_code",
    "first_name",
    "last_name",
    "email",
    "job_title",
    "department",
    "country_code",
    "currency",
    "salary",
    "employment_type",
    "hire_date",
    "status",
)


@dataclass(frozen=True)
class EmployeeFilters:
    q: str | None = None
    country: str | None = None
    department: str | None = None
    job_title: str | None = None
    status: str | None = None
    employment_type: str | None = None


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _build_query(filters: EmployeeFilters, sort: str) -> Select:
    stmt = select(Employee)
    if filters.q and filters.q.strip():
        pattern = f"%{_escape_like(filters.q.strip().lower())}%"
        stmt = stmt.where(
            func.lower(Employee.first_name).like(pattern, escape="\\")
            | func.lower(Employee.last_name).like(pattern, escape="\\")
            | func.lower(Employee.email).like(pattern, escape="\\")
            | func.lower(Employee.employee_code).like(pattern, escape="\\")
        )
    exact = {
        Employee.country_code: filters.country,
        Employee.department: filters.department,
        Employee.job_title: filters.job_title,
        Employee.status: filters.status,
        Employee.employment_type: filters.employment_type,
    }
    for column, value in exact.items():
        if value:
            stmt = stmt.where(column == value)
    return stmt.order_by(*_order_by(sort))


def _order_by(sort: str) -> list:
    descending = sort.startswith("-")
    field = sort.lstrip("-")
    if field not in SORTABLE_FIELDS:
        raise UnprocessableError(
            ["query", "sort"], f"sort must be one of: {', '.join(SORTABLE_FIELDS)}"
        )
    column = getattr(Employee, field)
    primary = column.desc() if descending else column.asc()
    # id as tie-breaker keeps pagination stable.
    return [primary] if field == "id" else [primary, Employee.id.asc()]


def list_employees(
    db: Session, filters: EmployeeFilters, sort: str, page: int, page_size: int
) -> tuple[list[Employee], int]:
    stmt = _build_query(filters, sort)
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    items = db.scalars(stmt.limit(page_size).offset((page - 1) * page_size)).all()
    return list(items), total


def _csv_safe(value: object) -> object:
    """Neutralise spreadsheet formula injection for text cells."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def export_csv(db: Session, filters: EmployeeFilters, sort: str) -> str:
    stmt = _build_query(filters, sort)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_COLUMNS)
    for employee in db.scalars(stmt).yield_per(1000):
        row = [getattr(employee, column) for column in CSV_COLUMNS]
        row[CSV_COLUMNS.index("salary")] = f"{employee.salary:.2f}"
        row[CSV_COLUMNS.index("hire_date")] = employee.hire_date.isoformat()
        writer.writerow([_csv_safe(cell) for cell in row])
    return buffer.getvalue()


def get_employee(db: Session, employee_id: int) -> Employee:
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise NotFoundError(f"Employee {employee_id} not found")
    return employee


def _ensure_email_available(db: Session, email: str, exclude_id: int | None = None) -> None:
    stmt = select(Employee.id).where(Employee.email == email)
    if exclude_id is not None:
        stmt = stmt.where(Employee.id != exclude_id)
    if db.scalar(stmt) is not None:
        raise ConflictError(f"An employee with email {email} already exists")


def create_employee(db: Session, data: EmployeeCreate) -> Employee:
    _ensure_email_available(db, data.email)
    employee = Employee(
        **data.model_dump(),
        currency=currency_for(data.country_code),
        employee_code="PENDING",
        status=EmployeeStatus.ACTIVE.value,
    )
    db.add(employee)
    try:
        db.flush()
        employee.employee_code = f"ACME-{employee.id:05d}"
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(f"An employee with email {data.email} already exists") from exc
    return employee


def update_employee(db: Session, employee_id: int, data: EmployeeUpdate, actor: User) -> Employee:
    employee = get_employee(db, employee_id)
    changes = data.model_dump(exclude_unset=True)
    new_salary = changes.pop("salary", None)
    reason = changes.pop("salary_change_reason", None)
    effective_date = changes.pop("salary_effective_date", None)

    if "email" in changes and changes["email"] != employee.email:
        _ensure_email_available(db, changes["email"], exclude_id=employee.id)
    if "country_code" in changes:
        employee.currency = currency_for(changes["country_code"])
    for field, value in changes.items():
        setattr(employee, field, value)

    if new_salary is not None and new_salary != employee.salary:
        _record_salary_change(db, employee, new_salary, reason, effective_date, actor)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("An employee with that email already exists") from exc
    return employee


def _record_salary_change(
    db: Session,
    employee: Employee,
    new_salary: float,
    reason: str | None,
    effective_date: date | None,
    actor: User,
) -> None:
    reason = (reason or "").strip()
    if not reason:
        raise UnprocessableError(
            ["body", "salary_change_reason"], "salary_change_reason is required to change salary"
        )
    if effective_date is None:
        raise UnprocessableError(
            ["body", "salary_effective_date"], "salary_effective_date is required to change salary"
        )
    db.add(
        SalaryChange(
            employee_id=employee.id,
            old_salary=employee.salary,
            new_salary=new_salary,
            effective_date=effective_date,
            reason=reason[:500],
            changed_by_user_id=actor.id,
        )
    )
    employee.salary = new_salary


def terminate_employee(db: Session, employee_id: int) -> Employee:
    employee = get_employee(db, employee_id)
    if employee.status != EmployeeStatus.TERMINATED.value:
        employee.status = EmployeeStatus.TERMINATED.value
        db.commit()
    return employee


def salary_history(db: Session, employee_id: int) -> list[SalaryChange]:
    get_employee(db, employee_id)
    stmt = (
        select(SalaryChange)
        .where(SalaryChange.employee_id == employee_id)
        .order_by(SalaryChange.effective_date.desc(), SalaryChange.id.desc())
    )
    return list(db.scalars(stmt).all())
