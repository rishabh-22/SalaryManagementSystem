"""Pay insights. Only active employees count; money never crosses countries."""

from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import EmployeeStatus
from app.core.errors import NotFoundError
from app.core.reference import COUNTRIES
from app.models import Employee
from app.services import stats

_ACTIVE = Employee.status == EmployeeStatus.ACTIVE.value


def _require_country(code: str) -> str:
    code = code.upper()
    if code not in COUNTRIES:
        raise NotFoundError(f"Unknown country code: {code}")
    return code


def _group(rows: list[tuple]) -> dict[str, list[float]]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for key, salary in rows:
        grouped[key].append(salary)
    return grouped


def _by_headcount(items: list[dict], name_key: str) -> list[dict]:
    return sorted(items, key=lambda i: (-i["headcount"], i[name_key]))


def _count_by(db: Session, column) -> list[tuple[str, int]]:
    stmt = select(column, func.count()).where(_ACTIVE).group_by(column)
    return [(key, count) for key, count in db.execute(stmt).all()]


def overview(db: Session) -> dict:
    salary_rows = db.execute(select(Employee.country_code, Employee.salary).where(_ACTIVE)).all()
    by_country = []
    for code, salaries in _group(salary_rows).items():
        summary = stats.summarize(salaries)
        by_country.append(
            {
                "country_code": code,
                "currency": COUNTRIES[code]["currency"],
                "headcount": summary["headcount"],
                "median_salary": summary["median"],
                "mean_salary": summary["mean"],
            }
        )
    by_department = [
        {"department": key, "headcount": count} for key, count in _count_by(db, Employee.department)
    ]
    by_type = [
        {"employment_type": key, "headcount": count}
        for key, count in _count_by(db, Employee.employment_type)
    ]
    return {
        "total_headcount": len(salary_rows),
        "by_country": _by_headcount(by_country, "country_code"),
        "by_department": _by_headcount(by_department, "department"),
        "by_employment_type": _by_headcount(by_type, "employment_type"),
    }


def _active_in_country(code: str, *columns):
    return select(*columns).where(_ACTIVE, Employee.country_code == code)


def country_insights(db: Session, code: str) -> dict:
    code = _require_country(code)
    rows = db.execute(
        _active_in_country(code, Employee.department, Employee.job_title, Employee.salary)
    ).all()
    by_department = _group([(dept, salary) for dept, _, salary in rows])
    by_title = _group([(title, salary) for _, title, salary in rows])

    def summaries(groups: dict[str, list[float]], name_key: str) -> list[dict]:
        items = [{name_key: name, "summary": stats.summarize(v)} for name, v in groups.items()]
        return sorted(items, key=lambda i: (-i["summary"]["headcount"], i[name_key]))

    return {
        "country_code": code,
        "currency": COUNTRIES[code]["currency"],
        "summary": stats.summarize([salary for _, _, salary in rows]),
        "by_department": summaries(by_department, "department"),
        "by_job_title": summaries(by_title, "job_title"),
    }


def distribution(db: Session, code: str, bins: int) -> dict:
    code = _require_country(code)
    salaries = list(db.scalars(_active_in_country(code, Employee.salary)).all())
    return {
        "country_code": code,
        "currency": COUNTRIES[code]["currency"],
        "bins": stats.histogram(salaries, bins),
    }


MIN_GROUP_SIZE_FOR_OUTLIERS = 3


def outliers(db: Session, code: str, threshold: float, limit: int) -> dict:
    code = _require_country(code)
    rows = db.execute(
        _active_in_country(
            code,
            Employee.id,
            Employee.employee_code,
            Employee.first_name,
            Employee.last_name,
            Employee.job_title,
            Employee.salary,
        )
    ).all()
    by_title: dict[str, list] = defaultdict(list)
    for row in rows:
        by_title[row.job_title].append(row)

    found = []
    for title, members in by_title.items():
        if len(members) < MIN_GROUP_SIZE_FOR_OUTLIERS:
            continue
        median = stats.summarize([m.salary for m in members])["median"]
        for m in members:
            dev = stats.deviation(m.salary, median)
            if abs(dev) > threshold:
                found.append(
                    {
                        "employee_id": m.id,
                        "employee_code": m.employee_code,
                        "full_name": f"{m.first_name} {m.last_name}",
                        "job_title": title,
                        "salary": round(m.salary, 2),
                        "job_title_median": median,
                        "deviation": dev,
                    }
                )
    found.sort(key=lambda o: (-abs(o["deviation"]), o["employee_id"]))
    return {
        "country_code": code,
        "currency": COUNTRIES[code]["currency"],
        "threshold": threshold,
        "items": found[:limit],
    }
