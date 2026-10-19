from datetime import date

from pydantic import BaseModel, ConfigDict, model_validator

from app.core.enums import EmployeeStatus, EmploymentType
from app.schemas.common import (
    CountryCode,
    Department,
    Email,
    JobTitle,
    Name,
    Salary,
    UTCDatetime,
)


class EmployeeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_code: str
    first_name: str
    last_name: str
    email: str
    job_title: str
    department: str
    country_code: str
    currency: str
    salary: float
    employment_type: EmploymentType
    hire_date: date
    status: EmployeeStatus
    created_at: UTCDatetime
    updated_at: UTCDatetime


class EmployeePage(BaseModel):
    items: list[EmployeeOut]
    total: int
    page: int
    page_size: int


class EmployeeCreate(BaseModel):
    first_name: Name
    last_name: Name
    email: Email
    job_title: JobTitle
    department: Department
    country_code: CountryCode
    employment_type: EmploymentType
    hire_date: date
    salary: Salary


class EmployeeUpdate(BaseModel):
    first_name: Name | None = None
    last_name: Name | None = None
    email: Email | None = None
    job_title: JobTitle | None = None
    department: Department | None = None
    country_code: CountryCode | None = None
    employment_type: EmploymentType | None = None
    hire_date: date | None = None
    status: EmployeeStatus | None = None
    salary: Salary | None = None
    salary_change_reason: str | None = None
    salary_effective_date: date | None = None

    @model_validator(mode="after")
    def _no_explicit_nulls(self) -> "EmployeeUpdate":
        nullable = {"salary_change_reason", "salary_effective_date"}
        for name in self.model_fields_set - nullable:
            if getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class ChangedBy(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str


class SalaryChangeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_id: int
    old_salary: float
    new_salary: float
    effective_date: date
    reason: str
    changed_by: ChangedBy | None
    created_at: UTCDatetime
