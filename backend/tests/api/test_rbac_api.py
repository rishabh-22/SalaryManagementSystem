# ruff: noqa: E501
"""Role x endpoint matrix. 'allowed' means the request is not rejected by authn/authz."""
import pytest

from tests.conftest import headers_for

ROLES = ["admin", "hr_manager", "viewer"]
ALL = {"admin", "hr_manager", "viewer"}
WRITERS = {"admin", "hr_manager"}
ADMIN_ONLY = {"admin"}

# (method, path template, json body factory name or None, allowed roles)
# {emp} -> existing employee id, {other} -> a user id that is not the caller
ENDPOINTS = [
    ("GET", "/api/meta", None, ALL),
    ("GET", "/api/auth/me", None, ALL),
    ("GET", "/api/employees", None, ALL),
    ("GET", "/api/employees/export.csv", None, ALL),
    ("GET", "/api/employees/{emp}", None, ALL),
    ("GET", "/api/employees/{emp}/salary-history", None, ALL),
    ("POST", "/api/employees", "new_employee", WRITERS),
    ("PATCH", "/api/employees/{emp}", "patch_name", WRITERS),
    ("DELETE", "/api/employees/{emp}", None, WRITERS),
    ("GET", "/api/insights/overview", None, ALL),
    ("GET", "/api/insights/country/US", None, ALL),
    ("GET", "/api/insights/country/US/distribution", None, ALL),
    ("GET", "/api/insights/country/US/outliers", None, ALL),
    ("GET", "/api/users", None, ADMIN_ONLY),
    ("POST", "/api/users", "new_user", ADMIN_ONLY),
    ("PATCH", "/api/users/{other}", "patch_user", ADMIN_ONLY),
    ("DELETE", "/api/users/{other}", None, ADMIN_ONLY),
]

PUBLIC_WRITE_OR_READ = [(m, p) for m, p, _, _ in ENDPOINTS]


@pytest.fixture()
def world(make_user, make_employee):
    emp = make_employee()
    other = make_user("viewer", email="victim@test.com")
    return {"emp": emp.id, "other": other.id}


BODIES = {
    "new_employee": lambda: {
        "first_name": "Zed", "last_name": "Zee", "email": "zed@acme.com",
        "job_title": "Software Engineer", "department": "Engineering",
        "country_code": "US", "employment_type": "full_time",
        "hire_date": "2022-02-02", "salary": 90000,
    },
    "patch_name": lambda: {"first_name": "Renamed"},
    "new_user": lambda: {
        "email": "fresh@test.com", "full_name": "Fresh", "password": "LongEnough1!", "role": "viewer",
    },
    "patch_user": lambda: {"full_name": "Renamed User"},
}


def _call(client, method, path, body_name, headers, world):
    url = path.format(**world)
    kwargs = {"headers": headers}
    if body_name:
        kwargs["json"] = BODIES[body_name]()
    return client.request(method, url, **kwargs)


@pytest.mark.parametrize("method,path,body,allowed", ENDPOINTS)
@pytest.mark.parametrize("role", ROLES)
def test_role_matrix(client, make_user, world, role, method, path, body, allowed):
    user = make_user(role, email=f"caller-{role}@test.com")
    r = _call(client, method, path, body, headers_for(user), world)
    if role in allowed:
        assert r.status_code not in (401, 403), f"{role} {method} {path} -> {r.status_code} {r.text}"
    else:
        assert r.status_code == 403, f"{role} {method} {path} -> {r.status_code}"


@pytest.mark.parametrize("method,path,body,allowed", ENDPOINTS)
def test_no_token_is_401(client, world, method, path, body, allowed):
    r = _call(client, method, path, body, {}, world)
    assert r.status_code == 401


def test_viewer_write_attempts_leave_data_untouched(client, viewer_h, make_employee):
    emp = make_employee(first_name="Keep")
    client.patch(f"/api/employees/{emp.id}", json={"first_name": "Hacked", "salary": 1}, headers=viewer_h)
    client.delete(f"/api/employees/{emp.id}", headers=viewer_h)
    after = client.get(f"/api/employees/{emp.id}", headers=viewer_h).json()
    assert after["first_name"] == "Keep" and after["status"] == "active" and after["salary"] == 100000.0
