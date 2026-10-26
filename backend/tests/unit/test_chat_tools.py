from datetime import date

import pytest

from app.core.errors import NotFoundError
from app.models import SalaryChange
from app.services.chat_tools import ToolError, previous_quarter, run_tool

TODAY = date(2026, 10, 26)


@pytest.fixture()
def add_change(db):
    def _add(employee, old, new, effective, reason="Annual review"):
        db.add(
            SalaryChange(
                employee_id=employee.id,
                old_salary=old,
                new_salary=new,
                effective_date=effective,
                reason=reason,
            )
        )
        db.commit()

    return _add


@pytest.mark.parametrize(
    ("today", "expected"),
    [
        (date(2026, 10, 26), (date(2026, 7, 1), date(2026, 9, 30))),
        (date(2026, 1, 5), (date(2025, 10, 1), date(2025, 12, 31))),
        (date(2026, 4, 1), (date(2026, 1, 1), date(2026, 3, 31))),
        (date(2026, 7, 31), (date(2026, 4, 1), date(2026, 6, 30))),
        (date(2026, 12, 31), (date(2026, 7, 1), date(2026, 9, 30))),
    ],
)
def test_previous_quarter(today, expected):
    assert previous_quarter(today) == expected


def test_get_current_date_reports_previous_quarter(db):
    result = run_tool(db, "get_current_date", {}, TODAY)
    assert result == {
        "today": "2026-10-26",
        "previous_quarter_start": "2026-07-01",
        "previous_quarter_end": "2026-09-30",
    }


def test_search_by_single_name_returns_all_matches(db, make_employee):
    a = make_employee(first_name="Ana", last_name="Silva")
    b = make_employee(first_name="Ana", last_name="Costa")
    make_employee(first_name="Bob", last_name="Stone")
    result = run_tool(db, "search_employees", {"query": "ana"}, TODAY)
    assert result["total_matches"] == 2
    assert {e["employee_id"] for e in result["employees"]} == {a.id, b.id}


def test_search_by_full_name_narrows_to_one(db, make_employee):
    make_employee(first_name="Ana", last_name="Costa")
    target = make_employee(first_name="Ana", last_name="Silva")
    result = run_tool(db, "search_employees", {"query": "Ana Silva"}, TODAY)
    assert [e["employee_id"] for e in result["employees"]] == [target.id]


def test_search_no_match_and_blank_query(db):
    assert run_tool(db, "search_employees", {"query": "nobody"}, TODAY)["total_matches"] == 0
    with pytest.raises(ToolError):
        run_tool(db, "search_employees", {"query": "  "}, TODAY)


def test_get_employee_salary(db, make_employee):
    e = make_employee(country_code="IN", salary=2500000.456)
    result = run_tool(db, "get_employee_salary", {"employee_id": e.id}, TODAY)
    assert result["salary"] == 2500000.46
    assert result["currency"] == "INR"
    assert result["employee_code"] == e.employee_code


def test_get_employee_salary_unknown_and_bad_id(db):
    with pytest.raises(NotFoundError):
        run_tool(db, "get_employee_salary", {"employee_id": 999}, TODAY)
    with pytest.raises(ToolError):
        run_tool(db, "get_employee_salary", {"employee_id": "5"}, TODAY)


def test_get_salary_history_newest_first(db, make_employee, add_change):
    e = make_employee()
    add_change(e, 90000, 95000, date(2025, 1, 1))
    add_change(e, 95000, 100000, date(2026, 1, 1), "Promotion")
    result = run_tool(db, "get_salary_history", {"employee_id": e.id}, TODAY)
    assert result["total_changes"] == 2
    assert result["changes"][0]["reason"] == "Promotion"
    assert result["changes"][0]["new_salary"] == 100000


def test_average_pay_by_country_counts_only_active(db, make_employee):
    make_employee(country_code="IN", salary=100)
    make_employee(country_code="IN", salary=300)
    make_employee(country_code="IN", salary=9999, status="terminated")
    make_employee(country_code="US", salary=50000)
    result = run_tool(db, "get_average_pay", {"country_code": "in"}, TODAY)
    assert result["currency"] == "INR"
    assert result["summary"]["headcount"] == 2
    assert result["summary"]["mean"] == 200


def test_average_pay_by_job_title_never_mixes_currencies(db, make_employee):
    make_employee(country_code="US", job_title="Software Engineer", salary=100000)
    make_employee(country_code="US", job_title="Software Engineer", salary=120000)
    make_employee(country_code="IN", job_title="Software Engineer", salary=2000000)
    make_employee(country_code="US", job_title="Data Analyst", salary=1)
    result = run_tool(db, "get_average_pay", {"job_title": "software engineer"}, TODAY)
    by_country = {r["country_code"]: r for r in result["by_country"]}
    assert set(by_country) == {"US", "IN"}
    assert by_country["US"]["currency"] == "USD"
    assert by_country["US"]["summary"]["mean"] == 110000
    assert by_country["IN"]["currency"] == "INR"
    assert by_country["IN"]["summary"]["mean"] == 2000000


def test_average_pay_job_title_within_country(db, make_employee):
    make_employee(country_code="US", job_title="Software Engineer", salary=100000)
    make_employee(country_code="IN", job_title="Software Engineer", salary=2000000)
    result = run_tool(
        db, "get_average_pay", {"job_title": "Software Engineer", "country_code": "IN"}, TODAY
    )
    assert [r["country_code"] for r in result["by_country"]] == ["IN"]


def test_average_pay_validation(db):
    with pytest.raises(ToolError):
        run_tool(db, "get_average_pay", {}, TODAY)
    with pytest.raises(NotFoundError):
        run_tool(db, "get_average_pay", {"country_code": "ZZ"}, TODAY)


def test_list_salary_revisions_filters_by_date_and_country(db, make_employee, add_change):
    inside_us = make_employee(first_name="In", last_name="Us", country_code="US")
    inside_in = make_employee(first_name="In", last_name="India", country_code="IN")
    before = make_employee(first_name="Too", last_name="Early")
    after = make_employee(first_name="Too", last_name="Late")
    add_change(inside_us, 100, 110, date(2026, 7, 1))
    add_change(inside_in, 200, 250, date(2026, 9, 30))
    add_change(before, 100, 110, date(2026, 6, 30))
    add_change(after, 100, 110, date(2026, 10, 1))

    args = {"start_date": "2026-07-01", "end_date": "2026-09-30"}
    result = run_tool(db, "list_salary_revisions", args, TODAY)
    assert result["total_revisions"] == 2
    assert {r["employee_id"] for r in result["revisions"]} == {inside_us.id, inside_in.id}
    india = next(r for r in result["revisions"] if r["country_code"] == "IN")
    assert india["change_pct"] == 25.0
    assert india["currency"] == "INR"

    only_in = run_tool(db, "list_salary_revisions", {**args, "country_code": "in"}, TODAY)
    assert [r["employee_id"] for r in only_in["revisions"]] == [inside_in.id]


def test_list_salary_revisions_bad_dates(db):
    with pytest.raises(ToolError):
        run_tool(
            db, "list_salary_revisions", {"start_date": "nope", "end_date": "2026-01-01"}, TODAY
        )
    with pytest.raises(ToolError):
        run_tool(
            db,
            "list_salary_revisions",
            {"start_date": "2026-02-01", "end_date": "2026-01-01"},
            TODAY,
        )


def test_unknown_tool(db):
    with pytest.raises(ToolError):
        run_tool(db, "drop_tables", {}, TODAY)
