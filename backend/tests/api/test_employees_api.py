# ruff: noqa: E501
import csv
import io

import pytest
from sqlalchemy import select

from app.models import SalaryChange

URL = "/api/employees"


def ids(resp):
    return [e["id"] for e in resp.json()["items"]]


# ---------- list: pagination ----------

def test_list_defaults_and_envelope(client, viewer_h, make_employee):
    for _ in range(3):
        make_employee()
    r = client.get(URL, headers=viewer_h)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3 and body["page"] == 1 and body["page_size"] == 25
    assert ids(r) == [1, 2, 3]


def test_list_pagination_slices(client, viewer_h, make_employee):
    for _ in range(5):
        make_employee()
    r1 = client.get(URL, params={"page": 1, "page_size": 2}, headers=viewer_h)
    r3 = client.get(URL, params={"page": 3, "page_size": 2}, headers=viewer_h)
    r9 = client.get(URL, params={"page": 9, "page_size": 2}, headers=viewer_h)
    assert ids(r1) == [1, 2] and r1.json()["total"] == 5
    assert ids(r3) == [5]
    assert r9.status_code == 200 and ids(r9) == [] and r9.json()["total"] == 5


@pytest.mark.parametrize("params", [
    {"page": 0}, {"page": -1}, {"page_size": 0}, {"page_size": 101}, {"page": "abc"},
])
def test_list_rejects_bad_pagination(client, viewer_h, params):
    assert client.get(URL, params=params, headers=viewer_h).status_code == 422


def test_list_page_size_100_allowed(client, viewer_h):
    assert client.get(URL, params={"page_size": 100}, headers=viewer_h).status_code == 200


# ---------- list: search and filters ----------

def test_search_matches_name_email_code_case_insensitively(client, viewer_h, make_employee):
    a = make_employee(first_name="Alice", last_name="Wonder", email="alice@acme.com")
    b = make_employee(first_name="Bob", last_name="Builder", email="bob@other.org")
    assert ids(client.get(URL, params={"q": "ALIC"}, headers=viewer_h)) == [a.id]
    assert ids(client.get(URL, params={"q": "builder"}, headers=viewer_h)) == [b.id]
    assert ids(client.get(URL, params={"q": "other.org"}, headers=viewer_h)) == [b.id]
    assert ids(client.get(URL, params={"q": "acme-00001"}, headers=viewer_h)) == [a.id]
    assert ids(client.get(URL, params={"q": "zzz"}, headers=viewer_h)) == []


def test_search_treats_like_wildcards_literally(client, viewer_h, make_employee):
    make_employee(first_name="Alice")
    assert ids(client.get(URL, params={"q": "%"}, headers=viewer_h)) == []
    assert ids(client.get(URL, params={"q": "_lice"}, headers=viewer_h)) == []


@pytest.fixture()
def mixed(make_employee):
    return {
        "us_eng": make_employee(country_code="US", department="Engineering", job_title="Software Engineer"),
        "in_eng": make_employee(country_code="IN", department="Engineering", job_title="Software Engineer",
                                employment_type="contract"),
        "us_sales": make_employee(country_code="US", department="Sales", job_title="Account Executive",
                                  employment_type="part_time"),
        "us_gone": make_employee(country_code="US", department="Sales", job_title="Account Executive",
                                 status="terminated"),
    }


@pytest.mark.parametrize("params,expected", [
    ({"country": "US"}, {"us_eng", "us_sales", "us_gone"}),
    ({"country": "IN"}, {"in_eng"}),
    ({"department": "Sales"}, {"us_sales", "us_gone"}),
    ({"job_title": "Software Engineer"}, {"us_eng", "in_eng"}),
    ({"status": "terminated"}, {"us_gone"}),
    ({"status": "active"}, {"us_eng", "in_eng", "us_sales"}),
    ({"employment_type": "contract"}, {"in_eng"}),
    ({"country": "US", "department": "Sales", "status": "active"}, {"us_sales"}),
    ({"country": "DE"}, set()),
])
def test_filters(client, viewer_h, mixed, params, expected):
    r = client.get(URL, params=params, headers=viewer_h)
    assert r.status_code == 200
    assert set(ids(r)) == {mixed[k].id for k in expected}
    assert r.json()["total"] == len(expected)


def test_list_includes_terminated_by_default(client, viewer_h, mixed):
    assert client.get(URL, headers=viewer_h).json()["total"] == 4


def test_invalid_enum_filter_is_422_or_empty(client, viewer_h, mixed):
    r = client.get(URL, params={"status": "bogus"}, headers=viewer_h)
    assert r.status_code == 422 or r.json()["total"] == 0


# ---------- list: sorting ----------

def test_sort_asc_desc_and_tie_break_by_id(client, viewer_h, make_employee):
    a = make_employee(salary=300)
    b = make_employee(salary=100)
    c = make_employee(salary=300)
    d = make_employee(salary=200)
    assert ids(client.get(URL, params={"sort": "salary"}, headers=viewer_h)) == [b.id, d.id, a.id, c.id]
    assert ids(client.get(URL, params={"sort": "-salary"}, headers=viewer_h)) == [a.id, c.id, d.id, b.id]


def test_sort_by_text_field(client, viewer_h, make_employee):
    z = make_employee(last_name="Zed")
    a = make_employee(last_name="Abe")
    assert ids(client.get(URL, params={"sort": "last_name"}, headers=viewer_h)) == [a.id, z.id]
    assert ids(client.get(URL, params={"sort": "-id"}, headers=viewer_h)) == [a.id, z.id]


@pytest.mark.parametrize("field", [
    "id", "employee_code", "first_name", "last_name", "job_title", "department",
    "country_code", "salary", "hire_date", "status",
])
def test_every_allowed_sort_field_works(client, viewer_h, make_employee, field):
    make_employee()
    assert client.get(URL, params={"sort": field}, headers=viewer_h).status_code == 200
    assert client.get(URL, params={"sort": f"-{field}"}, headers=viewer_h).status_code == 200


@pytest.mark.parametrize("sort", ["bogus", "-bogus", "hashed_password", "email; DROP TABLE employees", "salary,id"])
def test_unknown_sort_field_is_422(client, viewer_h, sort):
    assert client.get(URL, params={"sort": sort}, headers=viewer_h).status_code == 422


# ---------- get one ----------

def test_get_employee_shape(client, viewer_h, make_employee):
    emp = make_employee(first_name="Ana", country_code="BR", salary=185000.5)
    body = client.get(f"{URL}/{emp.id}", headers=viewer_h).json()
    assert body["employee_code"] == "ACME-00001"
    assert body["currency"] == "BRL" and body["salary"] == 185000.5
    assert body["hire_date"] == "2020-01-15" and body["status"] == "active"
    for key in ("id", "first_name", "last_name", "email", "job_title", "department", "country_code",
                "employment_type", "created_at", "updated_at"):
        assert key in body


def test_get_unknown_employee_is_404(client, viewer_h):
    r = client.get(f"{URL}/999", headers=viewer_h)
    assert r.status_code == 404 and "detail" in r.json()


# ---------- create ----------

def test_create_derives_currency_and_code_and_defaults_active(client, hr_h, employee_payload):
    r = client.post(URL, json=employee_payload(), headers=hr_h)
    assert r.status_code == 201
    body = r.json()
    assert body["currency"] == "BRL"
    assert body["employee_code"] == f"ACME-{body['id']:05d}"
    assert body["status"] == "active" and body["salary"] == 185000.5


def test_create_ignores_client_supplied_currency_and_status(client, hr_h, employee_payload):
    r = client.post(URL, json=employee_payload(currency="JPY", status="terminated", employee_code="X"), headers=hr_h)
    assert r.status_code == 201
    assert r.json()["currency"] == "BRL" and r.json()["status"] == "active"
    assert r.json()["employee_code"].startswith("ACME-")


def test_create_rounds_salary_to_two_decimals(client, hr_h, employee_payload):
    r = client.post(URL, json=employee_payload(salary=1234.5678), headers=hr_h)
    assert r.status_code == 201 and r.json()["salary"] == 1234.57


def test_create_writes_no_salary_history(client, hr_h, db, employee_payload):
    emp_id = client.post(URL, json=employee_payload(), headers=hr_h).json()["id"]
    assert client.get(f"{URL}/{emp_id}/salary-history", headers=hr_h).json() == []
    assert db.scalars(select(SalaryChange)).all() == []


def test_create_duplicate_email_is_409(client, hr_h, employee_payload):
    assert client.post(URL, json=employee_payload(), headers=hr_h).status_code == 201
    r = client.post(URL, json=employee_payload(first_name="Other"), headers=hr_h)
    assert r.status_code == 409 and "detail" in r.json()


@pytest.mark.parametrize("override", [
    {"salary": 0}, {"salary": -5}, {"salary": "abc"},
    {"email": "not-an-email"},
    {"first_name": ""}, {"last_name": ""},
    {"country_code": "ZZ"}, {"department": "Underwater Basket Weaving"}, {"job_title": "Wizard"},
    {"employment_type": "freelance"},
    {"hire_date": "15/03/2021"},
])
def test_create_validation_errors_are_422(client, hr_h, employee_payload, override):
    r = client.post(URL, json=employee_payload(**override), headers=hr_h)
    assert r.status_code == 422
    assert isinstance(r.json()["detail"], list)


@pytest.mark.parametrize("missing", [
    "first_name", "last_name", "email", "job_title", "department",
    "country_code", "employment_type", "hire_date", "salary",
])
def test_create_missing_required_field_is_422(client, hr_h, employee_payload, missing):
    payload = employee_payload()
    del payload[missing]
    assert client.post(URL, json=payload, headers=hr_h).status_code == 422


# ---------- patch ----------

def test_patch_profile_fields(client, hr_h, make_employee):
    emp = make_employee(first_name="Old")
    r = client.patch(f"{URL}/{emp.id}", json={"first_name": "New", "department": "Sales"}, headers=hr_h)
    assert r.status_code == 200
    assert r.json()["first_name"] == "New" and r.json()["department"] == "Sales"
    assert r.json()["last_name"] == emp.last_name


def test_patch_unknown_employee_is_404(client, hr_h):
    assert client.patch(f"{URL}/999", json={"first_name": "x"}, headers=hr_h).status_code == 404


def test_patch_email_to_existing_is_409(client, hr_h, make_employee):
    a = make_employee(email="a@acme.com")
    make_employee(email="b@acme.com")
    assert client.patch(f"{URL}/{a.id}", json={"email": "b@acme.com"}, headers=hr_h).status_code == 409


@pytest.mark.parametrize("body", [{"salary": -1}, {"status": "zombie"}, {"country_code": "ZZ"}, {"email": "nope"}])
def test_patch_invalid_values_are_422(client, hr_h, make_employee, body):
    emp = make_employee()
    assert client.patch(f"{URL}/{emp.id}", json=body, headers=hr_h).status_code == 422


def test_patch_status_can_reactivate(client, hr_h, make_employee):
    emp = make_employee(status="terminated")
    r = client.patch(f"{URL}/{emp.id}", json={"status": "active"}, headers=hr_h)
    assert r.json()["status"] == "active"


# ---------- patch: salary change rule ----------

def _raise(client, headers, emp, **extra):
    body = {"salary": 110000, "salary_change_reason": "Annual review", "salary_effective_date": "2026-04-01"}
    body.update(extra)
    return client.patch(f"{URL}/{emp.id}", json=body, headers=headers)


def test_salary_change_writes_history_and_updates_employee(client, hr, hr_h, make_employee):
    emp = make_employee(salary=100000)
    r = _raise(client, hr_h, emp)
    assert r.status_code == 200 and r.json()["salary"] == 110000
    hist = client.get(f"{URL}/{emp.id}/salary-history", headers=hr_h).json()
    assert len(hist) == 1
    row = hist[0]
    assert (row["old_salary"], row["new_salary"]) == (100000.0, 110000.0)
    assert row["effective_date"] == "2026-04-01" and row["reason"] == "Annual review"
    assert row["employee_id"] == emp.id
    assert row["changed_by"] == {"id": hr.id, "full_name": hr.full_name}
    assert "created_at" in row and "id" in row


@pytest.mark.parametrize("drop,override", [
    ("salary_change_reason", None),
    (None, {"salary_change_reason": ""}),
    (None, {"salary_change_reason": "   "}),
    ("salary_effective_date", None),
])
def test_salary_change_without_reason_or_date_is_422_and_changes_nothing(
    client, hr_h, make_employee, drop, override
):
    emp = make_employee(salary=100000)
    body = {"salary": 110000, "salary_change_reason": "Review", "salary_effective_date": "2026-04-01"}
    if drop:
        del body[drop]
    if override:
        body.update(override)
    assert client.patch(f"{URL}/{emp.id}", json=body, headers=hr_h).status_code == 422
    assert client.get(f"{URL}/{emp.id}", headers=hr_h).json()["salary"] == 100000
    assert client.get(f"{URL}/{emp.id}/salary-history", headers=hr_h).json() == []


def test_salary_change_missing_both_is_422(client, hr_h, make_employee):
    emp = make_employee(salary=100000)
    assert client.patch(f"{URL}/{emp.id}", json={"salary": 120000}, headers=hr_h).status_code == 422


def test_same_salary_needs_no_reason_and_writes_no_history(client, hr_h, make_employee):
    emp = make_employee(salary=100000)
    r = client.patch(f"{URL}/{emp.id}", json={"salary": 100000, "first_name": "Same"}, headers=hr_h)
    assert r.status_code == 200 and r.json()["first_name"] == "Same"
    assert client.get(f"{URL}/{emp.id}/salary-history", headers=hr_h).json() == []


def test_failed_patch_is_atomic_when_email_conflicts(client, hr_h, make_employee):
    a = make_employee(email="a@acme.com", salary=100000)
    make_employee(email="b@acme.com")
    r = _raise(client, hr_h, a, email="b@acme.com")
    assert r.status_code == 409
    assert client.get(f"{URL}/{a.id}", headers=hr_h).json()["salary"] == 100000
    assert client.get(f"{URL}/{a.id}/salary-history", headers=hr_h).json() == []


def test_history_ordering_newest_effective_date_first_then_id(client, hr_h, make_employee):
    emp = make_employee(salary=100)
    _raise(client, hr_h, emp, salary=200, salary_effective_date="2026-01-01")
    _raise(client, hr_h, emp, salary=300, salary_effective_date="2026-06-01")
    _raise(client, hr_h, emp, salary=400, salary_effective_date="2026-06-01")
    hist = client.get(f"{URL}/{emp.id}/salary-history", headers=hr_h).json()
    assert [h["new_salary"] for h in hist] == [400, 300, 200]
    assert [h["old_salary"] for h in hist] == [300, 200, 100]


def test_history_for_unknown_employee_is_404(client, hr_h):
    assert client.get(f"{URL}/999/salary-history", headers=hr_h).status_code == 404


def test_country_change_updates_currency(client, hr_h, make_employee):
    emp = make_employee(country_code="US")
    r = client.patch(f"{URL}/{emp.id}", json={"country_code": "GB"}, headers=hr_h)
    assert r.json()["country_code"] == "GB" and r.json()["currency"] == "GBP"


def test_patch_cannot_set_currency_directly(client, hr_h, make_employee):
    emp = make_employee(country_code="US")
    r = client.patch(f"{URL}/{emp.id}", json={"currency": "JPY"}, headers=hr_h)
    assert r.status_code in (200, 422)
    assert client.get(f"{URL}/{emp.id}", headers=hr_h).json()["currency"] == "USD"


# ---------- delete ----------

def test_soft_delete_sets_terminated_and_keeps_row(client, hr_h, make_employee):
    emp = make_employee()
    r = client.delete(f"{URL}/{emp.id}", headers=hr_h)
    assert r.status_code == 200 and r.json()["status"] == "terminated" and r.json()["id"] == emp.id
    assert client.get(f"{URL}/{emp.id}", headers=hr_h).json()["status"] == "terminated"


def test_soft_delete_is_idempotent(client, hr_h, make_employee):
    emp = make_employee()
    assert client.delete(f"{URL}/{emp.id}", headers=hr_h).status_code == 200
    r = client.delete(f"{URL}/{emp.id}", headers=hr_h)
    assert r.status_code == 200 and r.json()["status"] == "terminated"


def test_delete_unknown_is_404(client, hr_h):
    assert client.delete(f"{URL}/999", headers=hr_h).status_code == 404


# ---------- export ----------

EXPORT_COLUMNS = [
    "employee_code", "first_name", "last_name", "email", "job_title", "department",
    "country_code", "currency", "salary", "employment_type", "hire_date", "status",
]


def _rows(resp):
    return list(csv.DictReader(io.StringIO(resp.text)))


def test_export_headers_and_columns(client, viewer_h, make_employee):
    make_employee(first_name="Ana", last_name="Silva", country_code="BR", salary=1500.5)
    r = client.get(f"{URL}/export.csv", headers=viewer_h)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert r.headers["content-disposition"] == 'attachment; filename="employees.csv"'
    assert r.text.splitlines()[0] == ",".join(EXPORT_COLUMNS)
    row = _rows(r)[0]
    assert row["employee_code"] == "ACME-00001" and row["currency"] == "BRL"
    assert float(row["salary"]) == 1500.5 and row["hire_date"] == "2020-01-15"


def test_export_applies_filters_and_sort_without_pagination(client, viewer_h, make_employee):
    for i in range(30):
        make_employee(country_code="US", salary=1000 + i)
    make_employee(country_code="IN", salary=5)
    rows = _rows(client.get(f"{URL}/export.csv", params={"country": "US", "sort": "-salary"}, headers=viewer_h))
    assert len(rows) == 30  # more than the default page size of 25
    salaries = [float(r["salary"]) for r in rows]
    assert salaries == sorted(salaries, reverse=True)


def test_export_search_filter(client, viewer_h, make_employee):
    make_employee(first_name="Needle")
    make_employee(first_name="Hay")
    rows = _rows(client.get(f"{URL}/export.csv", params={"q": "needle"}, headers=viewer_h))
    assert [r["first_name"] for r in rows] == ["Needle"]


def test_export_unknown_sort_is_422(client, viewer_h):
    assert client.get(f"{URL}/export.csv", params={"sort": "nope"}, headers=viewer_h).status_code == 422


def test_export_empty_has_header_only(client, viewer_h):
    r = client.get(f"{URL}/export.csv", headers=viewer_h)
    assert r.text.strip() == ",".join(EXPORT_COLUMNS)


def test_export_neutralises_csv_formula_injection(client, viewer_h, make_employee):
    """Spreadsheet-bound export: cells starting with = + - @ must not be executable."""
    make_employee(first_name="=HYPERLINK(1)")
    r = client.get(f"{URL}/export.csv", headers=viewer_h)
    assert _rows(r)[0]["first_name"][0] != "="
