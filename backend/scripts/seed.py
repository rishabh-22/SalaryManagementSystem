"""Seed synthetic data: `python -m scripts.seed [--reset] [--count 10000]` (run from backend/).

Deterministic (random.Random(42), Faker.seed(42)). All data is synthetic.
"""

import argparse
import os
import random
import time
from datetime import date, timedelta
from itertools import islice

from faker import Faker
from sqlalchemy import delete, func, insert, select
from sqlalchemy.orm import Session

from app.core.enums import EmployeeStatus, EmploymentType, Role
from app.core.reference import (
    COUNTRIES,
    JOB_TITLES,
    TITLE_DEPARTMENT,
    base_salary,
    currency_for,
)
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models import Employee, SalaryChange, User
from app.models.mixins import utcnow

SEED = 42
BATCH_SIZE = 2000
# Fixed "today" so hire dates and history stay reproducible across runs.
REFERENCE_DATE = date(2026, 10, 1)

COUNTRY_WEIGHTS = {"US": 28, "GB": 10, "IN": 20, "DE": 11, "CA": 8, "SG": 5, "AU": 8, "BR": 10}
EMPLOYMENT_TYPE_WEIGHTS = {
    EmploymentType.FULL_TIME.value: 85,
    EmploymentType.PART_TIME.value: 7,
    EmploymentType.CONTRACT.value: 8,
}
# Junior roles are more common than managers/counsel.
TITLE_WEIGHT_OVERRIDES = {
    "Engineering Manager": 1,
    "Operations Manager": 1,
    "Marketing Manager": 1,
    "Legal Counsel": 1,
    "Support Team Lead": 2,
    "Customer Support Agent": 6,
    "Software Engineer": 6,
    "Senior Software Engineer": 4,
}
ACTIVE_RATE = 0.95
HISTORY_RATE = 0.25
SALARY_SIGMA = 0.18
CHANGE_REASONS = ("Annual review", "Promotion", "Market adjustment", "Role change", "Retention")

DEMO_USERS = (
    ("admin@acme.com", "Ada Admin", Role.ADMIN, "SEED_ADMIN_PASSWORD", "Admin#12345"),
    ("hr@acme.com", "Hannah Reed", Role.HR_MANAGER, "SEED_HR_PASSWORD", "HrManager#12345"),
    ("viewer@acme.com", "Victor Viewer", Role.VIEWER, "SEED_VIEWER_PASSWORD", "Viewer#12345"),
)


def ensure_demo_users(db: Session) -> dict[str, int]:
    """Creates missing demo users (never overwrites existing ones); returns email -> id."""
    ids: dict[str, int] = {}
    for email, full_name, role, env_var, default in DEMO_USERS:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(
                email=email,
                full_name=full_name,
                role=role.value,
                hashed_password=hash_password(os.environ.get(env_var, default)),
            )
            db.add(user)
            db.flush()
        ids[email] = user.id
    db.commit()
    return ids


def _unique_email(first: str, last: str, taken: dict[str, int]) -> str:
    stem = "".join(c for c in f"{first}.{last}".lower() if c.isalnum() or c == ".")
    count = taken.get(stem, 0)
    taken[stem] = count + 1
    return f"{stem}@acme.com" if count == 0 else f"{stem}{count + 1}@acme.com"


def _salary_history(
    rng: random.Random, employee_id: int, hire_date: date, salary: float, author_id: int
) -> list[dict]:
    """Builds a chain of changes ending exactly at the employee's current salary."""
    span = (REFERENCE_DATE - hire_date).days
    if span < 120:
        return []
    count = rng.randint(1, 3)
    days = sorted(rng.sample(range(60, span), min(count, span - 60)))
    rows: list[dict] = []
    new = salary
    for offset in reversed(days):
        old = round(new / (1 + rng.uniform(0.02, 0.12)), 2)
        rows.append(
            {
                "employee_id": employee_id,
                "old_salary": old,
                "new_salary": new,
                "effective_date": hire_date + timedelta(days=offset),
                "reason": rng.choice(CHANGE_REASONS),
                "changed_by_user_id": author_id,
                "created_at": utcnow(),
            }
        )
        new = old
    return rows


def generate(count: int, author_id: int) -> tuple[list[dict], list[dict]]:
    rng = random.Random(SEED)
    fake = Faker()
    Faker.seed(SEED)

    countries = list(COUNTRY_WEIGHTS)
    country_weights = list(COUNTRY_WEIGHTS.values())
    titles = list(JOB_TITLES)
    title_weights = [TITLE_WEIGHT_OVERRIDES.get(t, 3) for t in titles]
    types = list(EMPLOYMENT_TYPE_WEIGHTS)
    type_weights = list(EMPLOYMENT_TYPE_WEIGHTS.values())

    taken: dict[str, int] = {}
    employees: list[dict] = []
    changes: list[dict] = []
    now = utcnow()
    for employee_id in range(1, count + 1):
        first, last = fake.first_name(), fake.last_name()
        country = rng.choices(countries, country_weights)[0]
        title = rng.choices(titles, title_weights)[0]
        salary = round(base_salary(title, country) * rng.lognormvariate(0, SALARY_SIGMA), 2)
        hire_date = REFERENCE_DATE - timedelta(days=rng.randint(30, 365 * 12))
        active = rng.random() < ACTIVE_RATE
        employees.append(
            {
                "id": employee_id,
                "employee_code": f"ACME-{employee_id:05d}",
                "first_name": first,
                "last_name": last,
                "email": _unique_email(first, last, taken),
                "job_title": title,
                "department": TITLE_DEPARTMENT[title],
                "country_code": country,
                "currency": currency_for(country),
                "salary": salary,
                "employment_type": rng.choices(types, type_weights)[0],
                "hire_date": hire_date,
                "status": (EmployeeStatus.ACTIVE if active else EmployeeStatus.TERMINATED).value,
                "created_at": now,
                "updated_at": now,
            }
        )
        if rng.random() < HISTORY_RATE:
            changes.extend(_salary_history(rng, employee_id, hire_date, salary, author_id))
    return employees, changes


def _insert_in_batches(db: Session, model, rows: list[dict]) -> None:
    iterator = iter(rows)
    while batch := list(islice(iterator, BATCH_SIZE)):
        db.execute(insert(model), batch)


def seed(db: Session, count: int = 10_000, reset: bool = False) -> int:
    """Returns the number of employees inserted (0 when skipped)."""
    Base.metadata.create_all(engine)
    existing = db.scalar(select(func.count()).select_from(Employee)) or 0
    if existing and not reset:
        ensure_demo_users(db)
        return 0
    if reset:
        db.execute(delete(SalaryChange))
        db.execute(delete(Employee))
        db.commit()
    user_ids = ensure_demo_users(db)
    employees, changes = generate(count, user_ids["hr@acme.com"])
    _insert_in_batches(db, Employee, employees)
    _insert_in_batches(db, SalaryChange, changes)
    db.commit()
    return len(employees)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed synthetic ACME employees.")
    parser.add_argument("--reset", action="store_true", help="delete existing employees first")
    parser.add_argument("--count", type=int, default=10_000, help="number of employees")
    args = parser.parse_args()

    started = time.perf_counter()
    with SessionLocal() as db:
        inserted = seed(db, count=args.count, reset=args.reset)
    elapsed = time.perf_counter() - started
    if inserted:
        print(f"Seeded {inserted} employees across {len(COUNTRIES)} countries in {elapsed:.2f}s")
    else:
        print("Employees already exist; nothing to do (use --reset to re-seed).")


if __name__ == "__main__":
    main()
