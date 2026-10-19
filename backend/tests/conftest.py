# ruff: noqa: E501
"""Shared fixtures: in-memory SQLite, TestClient, users per role, employee factory."""

from __future__ import annotations

import itertools
from collections.abc import Callable, Iterator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.reference import COUNTRIES
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.models import Employee, SalaryChange, User  # noqa: F401  (register tables)

PASSWORD = "Passw0rd!123"
_HASH_CACHE: dict[str, str] = {}


def _hash(password: str) -> str:
    """bcrypt is deliberately slow; hash each distinct password once per session."""
    if password not in _HASH_CACHE:
        _HASH_CACHE[password] = hash_password(password)
    return _HASH_CACHE[password]


def _currency(country_code: str) -> str:
    info = COUNTRIES[country_code]
    if isinstance(info, dict):
        return info["currency"]
    return getattr(info, "currency", info)


@pytest.fixture()
def engine():
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine) -> Iterator[Session]:
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    yield session
    session.close()


@pytest.fixture()
def client(engine) -> Iterator[TestClient]:
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_db() -> Iterator[Session]:
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def make_user(db: Session) -> Callable[..., User]:
    counter = itertools.count(1)

    def _make(
        role: str = "viewer",
        *,
        email: str | None = None,
        password: str = PASSWORD,
        is_active: bool = True,
        full_name: str | None = None,
    ) -> User:
        n = next(counter)
        user = User(
            email=email or f"{role}{n}@test.com",
            full_name=full_name or f"{role.title()} User {n}",
            hashed_password=_hash(password),
            role=role,
            is_active=is_active,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    return _make


def token_for(user: User) -> str:
    return create_access_token(str(user.id), user.role)


def headers_for(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {token_for(user)}"}


@pytest.fixture()
def admin(make_user) -> User:
    return make_user("admin", email="admin@test.com")


@pytest.fixture()
def hr(make_user) -> User:
    return make_user("hr_manager", email="hr@test.com")


@pytest.fixture()
def viewer(make_user) -> User:
    return make_user("viewer", email="viewer@test.com")


@pytest.fixture()
def admin_h(admin) -> dict[str, str]:
    return headers_for(admin)


@pytest.fixture()
def hr_h(hr) -> dict[str, str]:
    return headers_for(hr)


@pytest.fixture()
def viewer_h(viewer) -> dict[str, str]:
    return headers_for(viewer)


@pytest.fixture()
def make_employee(db: Session) -> Callable[..., Employee]:
    counter = itertools.count(1)

    def _make(
        *,
        first_name: str | None = None,
        last_name: str | None = None,
        email: str | None = None,
        job_title: str = "Software Engineer",
        department: str = "Engineering",
        country_code: str = "US",
        salary: float = 100000.0,
        employment_type: str = "full_time",
        hire_date: date = date(2020, 1, 15),
        status: str = "active",
    ) -> Employee:
        n = next(counter)
        emp = Employee(
            employee_code=f"ACME-{n:05d}",
            first_name=first_name or f"First{n}",
            last_name=last_name or f"Last{n}",
            email=email or f"person{n}@acme.com",
            job_title=job_title,
            department=department,
            country_code=country_code,
            currency=_currency(country_code),
            salary=salary,
            employment_type=employment_type,
            hire_date=hire_date,
            status=status,
        )
        db.add(emp)
        db.commit()
        db.refresh(emp)
        return emp

    return _make


@pytest.fixture()
def employee_payload() -> Callable[..., dict]:
    def _payload(**overrides) -> dict:
        data = {
            "first_name": "Ana",
            "last_name": "Silva",
            "email": "ana.silva@acme.com",
            "job_title": "Software Engineer",
            "department": "Engineering",
            "country_code": "BR",
            "employment_type": "full_time",
            "hire_date": "2021-03-15",
            "salary": 185000.5,
        }
        data.update(overrides)
        return data

    return _payload
