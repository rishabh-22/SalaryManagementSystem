from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import EmployeeStatus, EmploymentType
from app.db.base import Base
from app.models.mixins import utcnow


class Employee(Base):
    __tablename__ = "employees"
    __table_args__ = (Index("ix_employees_country_job_title", "country_code", "job_title"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    # Assigned after the insert, once the id is known (ACME-00001).
    employee_code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    job_title: Mapped[str] = mapped_column(String(100), index=True)
    department: Mapped[str] = mapped_column(String(100), index=True)
    country_code: Mapped[str] = mapped_column(String(2), index=True)
    currency: Mapped[str] = mapped_column(String(3))
    salary: Mapped[float] = mapped_column(Float)
    employment_type: Mapped[str] = mapped_column(String(20), default=EmploymentType.FULL_TIME.value)
    hire_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default=EmployeeStatus.ACTIVE.value, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
