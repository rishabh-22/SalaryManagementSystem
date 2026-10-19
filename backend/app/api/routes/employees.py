from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import CurrentUser, DbSession, WriteUser
from app.core.enums import EmployeeStatus, EmploymentType
from app.schemas.employee import (
    EmployeeCreate,
    EmployeeOut,
    EmployeePage,
    EmployeeUpdate,
    SalaryChangeOut,
)
from app.services import employee_service
from app.services.employee_service import EmployeeFilters

router = APIRouter(prefix="/employees", tags=["employees"])


def employee_filters(
    q: str | None = Query(None, max_length=100),
    country: str | None = None,
    department: str | None = None,
    job_title: str | None = None,
    status: EmployeeStatus | None = None,
    employment_type: EmploymentType | None = None,
) -> EmployeeFilters:
    return EmployeeFilters(
        q=q,
        country=country,
        department=department,
        job_title=job_title,
        status=status.value if status else None,
        employment_type=employment_type.value if employment_type else None,
    )


Filters = Annotated[EmployeeFilters, Depends(employee_filters)]


@router.get("", response_model=EmployeePage)
def list_employees(
    _: CurrentUser,
    db: DbSession,
    filters: Filters,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    sort: str = "id",
):
    items, total = employee_service.list_employees(db, filters, sort, page, page_size)
    return EmployeePage(items=items, total=total, page=page, page_size=page_size)


# Must be declared before "/{employee_id}".
@router.get("/export.csv")
def export_employees(_: CurrentUser, db: DbSession, filters: Filters, sort: str = "id") -> Response:
    content = employee_service.export_csv(db, filters, sort)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="employees.csv"'},
    )


@router.get("/{employee_id}", response_model=EmployeeOut)
def get_employee(employee_id: int, _: CurrentUser, db: DbSession):
    return employee_service.get_employee(db, employee_id)


@router.post("", response_model=EmployeeOut, status_code=status.HTTP_201_CREATED)
def create_employee(payload: EmployeeCreate, _: WriteUser, db: DbSession):
    return employee_service.create_employee(db, payload)


@router.patch("/{employee_id}", response_model=EmployeeOut)
def update_employee(employee_id: int, payload: EmployeeUpdate, actor: WriteUser, db: DbSession):
    return employee_service.update_employee(db, employee_id, payload, actor)


@router.delete("/{employee_id}", response_model=EmployeeOut)
def terminate_employee(employee_id: int, _: WriteUser, db: DbSession):
    return employee_service.terminate_employee(db, employee_id)


@router.get("/{employee_id}/salary-history", response_model=list[SalaryChangeOut])
def salary_history(employee_id: int, _: CurrentUser, db: DbSession):
    return employee_service.salary_history(db, employee_id)
