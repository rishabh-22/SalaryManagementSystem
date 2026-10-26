"""Read-only tools the chat agent can call. They reuse the existing services; nothing writes."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.services import employee_service, insights_service
from app.services.employee_service import EmployeeFilters

MAX_SEARCH_RESULTS = 10
MAX_HISTORY_ROWS = 20
MAX_REVISION_ROWS = 50
_SEARCH_CANDIDATES = 200


class ToolError(Exception):
    """Bad tool arguments or unknown tool; reported back to the model, not to the HTTP client."""


def previous_quarter(today: date) -> tuple[date, date]:
    """First and last day of the calendar quarter before the one containing `today`."""
    quarter = (today.month - 1) // 3
    year = today.year
    if quarter == 0:
        quarter, year = 4, year - 1
    start = date(year, 3 * (quarter - 1) + 1, 1)
    next_start = date(year + 1, 1, 1) if quarter == 4 else date(year, 3 * quarter + 1, 1)
    return start, next_start - timedelta(days=1)


def _employee_id(args: dict[str, Any]) -> int:
    value = args.get("employee_id")
    if isinstance(value, bool) or not isinstance(value, int):
        raise ToolError("employee_id must be an integer")
    return value


def _parse_date(args: dict[str, Any], key: str) -> date:
    try:
        return date.fromisoformat(str(args.get(key)))
    except ValueError as exc:
        raise ToolError(f"{key} must be an ISO date (YYYY-MM-DD)") from exc


def _employee_summary(e) -> dict[str, Any]:
    return {
        "employee_id": e.id,
        "employee_code": e.employee_code,
        "name": f"{e.first_name} {e.last_name}",
        "email": e.email,
        "job_title": e.job_title,
        "department": e.department,
        "country_code": e.country_code,
        "status": e.status,
    }


def search_employees(db: Session, args: dict[str, Any], today: date) -> dict[str, Any]:
    query = str(args.get("query", "")).strip()
    if not query:
        raise ToolError("query must not be empty")
    tokens = [t.lower() for t in query.split()]
    # The service searches one substring over name/email/code; narrow by the remaining tokens here
    # so "John Smith" works.
    candidates, _ = employee_service.list_employees(
        db, EmployeeFilters(q=tokens[0]), "id", 1, _SEARCH_CANDIDATES
    )
    matches = []
    for e in candidates:
        haystack = [e.first_name, e.last_name, e.email, e.employee_code]
        if all(any(t in field.lower() for field in haystack) for t in tokens[1:]):
            matches.append(e)
    return {
        "total_matches": len(matches),
        "employees": [_employee_summary(e) for e in matches[:MAX_SEARCH_RESULTS]],
    }


def get_employee_salary(db: Session, args: dict[str, Any], today: date) -> dict[str, Any]:
    e = employee_service.get_employee(db, _employee_id(args))
    return {
        **_employee_summary(e),
        "salary": round(e.salary, 2),
        "currency": e.currency,
        "hire_date": e.hire_date.isoformat(),
    }


def get_salary_history(db: Session, args: dict[str, Any], today: date) -> dict[str, Any]:
    employee_id = _employee_id(args)
    e = employee_service.get_employee(db, employee_id)
    history = employee_service.salary_history(db, employee_id)
    return {
        "employee_id": e.id,
        "name": f"{e.first_name} {e.last_name}",
        "currency": e.currency,
        "total_changes": len(history),
        "changes": [
            {
                "effective_date": c.effective_date.isoformat(),
                "old_salary": round(c.old_salary, 2),
                "new_salary": round(c.new_salary, 2),
                "reason": c.reason,
            }
            for c in history[:MAX_HISTORY_ROWS]
        ],
    }


def get_average_pay(db: Session, args: dict[str, Any], today: date) -> dict[str, Any]:
    country = (args.get("country_code") or "").strip() or None
    job_title = (args.get("job_title") or "").strip() or None
    if not country and not job_title:
        raise ToolError("provide country_code, job_title, or both")
    if job_title:
        return insights_service.pay_by_job_title(db, job_title, country)
    data = insights_service.country_insights(db, country)
    return {
        "country_code": data["country_code"],
        "currency": data["currency"],
        "summary": data["summary"],
    }


def list_salary_revisions(db: Session, args: dict[str, Any], today: date) -> dict[str, Any]:
    start, end = _parse_date(args, "start_date"), _parse_date(args, "end_date")
    if start > end:
        raise ToolError("start_date must not be after end_date")
    country = (args.get("country_code") or "").strip() or None
    rows, total = employee_service.salary_revisions(db, start, end, country, MAX_REVISION_ROWS)
    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "total_revisions": total,
        "shown": len(rows),
        "revisions": [
            {
                "employee_id": e.id,
                "name": f"{e.first_name} {e.last_name}",
                "job_title": e.job_title,
                "country_code": e.country_code,
                "currency": e.currency,
                "old_salary": round(c.old_salary, 2),
                "new_salary": round(c.new_salary, 2),
                "change_pct": round((c.new_salary - c.old_salary) / c.old_salary * 100, 2)
                if c.old_salary
                else None,
                "effective_date": c.effective_date.isoformat(),
                "reason": c.reason,
            }
            for c, e in rows
        ],
    }


def get_current_date(db: Session, args: dict[str, Any], today: date) -> dict[str, Any]:
    start, end = previous_quarter(today)
    return {
        "today": today.isoformat(),
        "previous_quarter_start": start.isoformat(),
        "previous_quarter_end": end.isoformat(),
    }


_TOOLS = {
    "search_employees": search_employees,
    "get_employee_salary": get_employee_salary,
    "get_salary_history": get_salary_history,
    "get_average_pay": get_average_pay,
    "list_salary_revisions": list_salary_revisions,
    "get_current_date": get_current_date,
}

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "search_employees",
        "description": (
            "Find employees by name, email or employee code "
            "(e.g. 'Ana', 'Ana Silva', 'ACME-00042'). "
            "Use this whenever the user gives a name instead of an employee id."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Name, email or code."}},
            "required": ["query"],
        },
    },
    {
        "name": "get_employee_salary",
        "description": "Get one employee's current annual salary (local currency) by numeric id.",
        "input_schema": {
            "type": "object",
            "properties": {"employee_id": {"type": "integer"}},
            "required": ["employee_id"],
        },
    },
    {
        "name": "get_salary_history",
        "description": "Get the salary change history of one employee by numeric id.",
        "input_schema": {
            "type": "object",
            "properties": {"employee_id": {"type": "integer"}},
            "required": ["employee_id"],
        },
    },
    {
        "name": "get_average_pay",
        "description": (
            "Average/median/min/max annual pay of active employees, for a country, a job title, "
            "or a job title within a country. Results are per country in local currency; never "
            "combine figures across currencies."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "country_code": {"type": "string", "description": "ISO code, e.g. IN, US."},
                "job_title": {"type": "string", "description": "Exact job title."},
            },
        },
    },
    {
        "name": "list_salary_revisions",
        "description": (
            "List salary revisions whose effective date falls in [start_date, end_date], "
            "optionally for one country."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "YYYY-MM-DD"},
                "country_code": {"type": "string"},
            },
            "required": ["start_date", "end_date"],
        },
    },
    {
        "name": "get_current_date",
        "description": (
            "Today's date and the start/end of the previous calendar quarter. Call this to "
            "resolve 'last quarter' instead of guessing dates."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
]


def run_tool(db: Session, name: str, args: dict[str, Any], today: date | None = None) -> dict:
    """Execute a tool. Raises ToolError/DomainError for the caller to report to the model."""
    handler = _TOOLS.get(name)
    if handler is None:
        raise ToolError(f"Unknown tool: {name}")
    return handler(db, args or {}, today or date.today())


TOOL_ERRORS = (ToolError, DomainError)
