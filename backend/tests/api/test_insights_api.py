# ruff: noqa: E501
"""Insights against a tiny dataset whose numbers are computed by hand.

Active US employees (USD), sorted:
    50000 (Account Executive, Sales, part_time)
    60000 (Account Executive, Sales)
    100000, 100000, 100000 (Software Engineer, Engineering)
    160000 (Software Engineer, Engineering)
  n=6, total=570000, mean=95000, median=100000
  p25 = 60000 + 0.25*(100000-60000) = 70000 ; p75 = 100000   (inclusive method)
Plus noise that must be ignored or kept separate:
    US terminated Software Engineer 1,000,000
    IN active Software Engineers 1,000,000 and 2,000,000 (INR)
    DE active Account Executive 80,000 (EUR)
"""
import pytest

BASE = "/api/insights"


@pytest.fixture()
def dataset(make_employee):
    se = dict(job_title="Software Engineer", department="Engineering")
    ae = dict(job_title="Account Executive", department="Sales")
    for s in (100000, 100000, 100000, 160000):
        make_employee(country_code="US", salary=s, **se)
    make_employee(country_code="US", salary=50000, employment_type="part_time", **ae)
    make_employee(country_code="US", salary=60000, **ae)
    make_employee(country_code="US", salary=1_000_000, status="terminated", **se)
    make_employee(country_code="IN", salary=1_000_000, **se)
    make_employee(country_code="IN", salary=2_000_000, **se)
    make_employee(country_code="DE", salary=80000, **ae)


# ---------- overview ----------

def test_overview_counts_only_active_and_sorts_by_headcount(client, viewer_h, dataset):
    body = client.get(f"{BASE}/overview", headers=viewer_h).json()
    assert body["total_headcount"] == 9
    assert body["by_country"] == [
        {"country_code": "US", "currency": "USD", "headcount": 6, "median_salary": 100000.0, "mean_salary": 95000.0},
        {"country_code": "IN", "currency": "INR", "headcount": 2, "median_salary": 1500000.0, "mean_salary": 1500000.0},
        {"country_code": "DE", "currency": "EUR", "headcount": 1, "median_salary": 80000.0, "mean_salary": 80000.0},
    ]
    assert body["by_department"] == [
        {"department": "Engineering", "headcount": 6},
        {"department": "Sales", "headcount": 3},
    ]
    assert body["by_employment_type"] == [
        {"employment_type": "full_time", "headcount": 8},
        {"employment_type": "part_time", "headcount": 1},
    ]


def test_overview_ties_sorted_by_name_ascending(client, viewer_h, make_employee):
    make_employee(country_code="IN", department="Sales")
    make_employee(country_code="BR", department="Finance")
    make_employee(country_code="CA", department="Design")
    body = client.get(f"{BASE}/overview", headers=viewer_h).json()
    assert [c["country_code"] for c in body["by_country"]] == ["BR", "CA", "IN"]
    assert [d["department"] for d in body["by_department"]] == ["Design", "Finance", "Sales"]


def test_overview_empty_database(client, viewer_h):
    body = client.get(f"{BASE}/overview", headers=viewer_h).json()
    assert body["total_headcount"] == 0
    assert body["by_country"] == [] and body["by_department"] == [] and body["by_employment_type"] == []


def test_overview_never_sums_money_across_currencies(client, viewer_h, dataset):
    raw = client.get(f"{BASE}/overview", headers=viewer_h).text
    assert "total_payroll" not in raw


# ---------- country summary ----------

def test_country_summary_numbers(client, viewer_h, dataset):
    body = client.get(f"{BASE}/country/US", headers=viewer_h).json()
    assert body["country_code"] == "US" and body["currency"] == "USD"
    assert body["summary"] == {
        "headcount": 6, "min": 50000.0, "p25": 70000.0, "median": 100000.0,
        "p75": 100000.0, "max": 160000.0, "mean": 95000.0, "total_payroll": 570000.0,
    }


def test_country_scoped_to_its_own_currency(client, viewer_h, dataset):
    india = client.get(f"{BASE}/country/IN", headers=viewer_h).json()
    assert india["currency"] == "INR"
    assert india["summary"]["headcount"] == 2
    assert india["summary"]["total_payroll"] == 3_000_000.0
    germany = client.get(f"{BASE}/country/DE", headers=viewer_h).json()
    assert germany["summary"]["max"] == 80000.0


def test_country_by_department_and_job_title(client, viewer_h, dataset):
    body = client.get(f"{BASE}/country/US", headers=viewer_h).json()
    eng, sales = body["by_department"]
    assert eng["department"] == "Engineering" and sales["department"] == "Sales"
    assert eng["summary"] == {
        "headcount": 4, "min": 100000.0, "p25": 100000.0, "median": 100000.0,
        "p75": 115000.0, "max": 160000.0, "mean": 115000.0, "total_payroll": 460000.0,
    }
    assert sales["summary"] == {
        "headcount": 2, "min": 50000.0, "p25": 52500.0, "median": 55000.0,
        "p75": 57500.0, "max": 60000.0, "mean": 55000.0, "total_payroll": 110000.0,
    }
    titles = [(t["job_title"], t["summary"]["headcount"]) for t in body["by_job_title"]]
    assert titles == [("Software Engineer", 4), ("Account Executive", 2)]


def test_country_groups_tie_broken_by_name_and_empty_groups_omitted(client, viewer_h, make_employee):
    make_employee(country_code="SG", department="Sales", job_title="Account Executive")
    make_employee(country_code="SG", department="Engineering", job_title="Software Engineer")
    make_employee(country_code="SG", department="Legal", job_title="Software Engineer", status="terminated")
    body = client.get(f"{BASE}/country/SG", headers=viewer_h).json()
    assert [d["department"] for d in body["by_department"]] == ["Engineering", "Sales"]
    assert [t["job_title"] for t in body["by_job_title"]] == ["Account Executive", "Software Engineer"]


def test_country_with_no_active_employees_has_null_summary(client, viewer_h, make_employee):
    make_employee(country_code="AU", status="terminated")
    body = client.get(f"{BASE}/country/AU", headers=viewer_h).json()
    assert body["currency"] == "AUD"
    assert body["summary"]["headcount"] == 0
    assert all(v is None for k, v in body["summary"].items() if k != "headcount")
    assert body["by_department"] == [] and body["by_job_title"] == []


def test_single_employee_country_percentiles_equal_salary(client, viewer_h, make_employee):
    make_employee(country_code="CA", salary=77777.77)
    s = client.get(f"{BASE}/country/CA", headers=viewer_h).json()["summary"]
    assert s["p25"] == s["median"] == s["p75"] == s["mean"] == s["min"] == s["max"] == 77777.77


def test_money_values_rounded_to_two_decimals(client, viewer_h, make_employee):
    for s in (100.0, 100.0, 100.01):
        make_employee(country_code="US", salary=s)
    s = client.get(f"{BASE}/country/US", headers=viewer_h).json()["summary"]
    assert s["mean"] == 100.0 and s["total_payroll"] == 300.01


# ---------- distribution ----------

def test_distribution_bins(client, viewer_h, dataset):
    body = client.get(f"{BASE}/country/US/distribution", params={"bins": 5}, headers=viewer_h).json()
    assert body["country_code"] == "US" and body["currency"] == "USD"
    got = [(b["lower"], b["upper"], b["count"]) for b in body["bins"]]
    expected = [(50000, 72000, 2), (72000, 94000, 0), (94000, 116000, 3), (116000, 138000, 0), (138000, 160000, 1)]
    assert len(got) == 5
    for (gl, gu, gc), (el, eu, ec) in zip(got, expected, strict=True):
        assert gl == pytest.approx(el) and gu == pytest.approx(eu) and gc == ec


def test_distribution_default_is_ten_bins_and_counts_sum_to_headcount(client, viewer_h, dataset):
    bins = client.get(f"{BASE}/country/US/distribution", headers=viewer_h).json()["bins"]
    assert len(bins) == 10 and sum(b["count"] for b in bins) == 6
    assert bins[-1]["upper"] == 160000.0 and bins[-1]["count"] >= 1  # max is inside the last bin


def test_distribution_all_equal_salaries_single_bin(client, viewer_h, make_employee):
    for _ in range(3):
        make_employee(country_code="US", salary=5000)
    bins = client.get(f"{BASE}/country/US/distribution", headers=viewer_h).json()["bins"]
    assert bins == [{"lower": 5000.0, "upper": 5000.0, "count": 3}]


def test_distribution_empty_country(client, viewer_h):
    assert client.get(f"{BASE}/country/US/distribution", headers=viewer_h).json()["bins"] == []


@pytest.mark.parametrize("bins", [0, 51, -3, "x"])
def test_distribution_bins_out_of_range_is_422(client, viewer_h, bins):
    assert client.get(f"{BASE}/country/US/distribution", params={"bins": bins}, headers=viewer_h).status_code == 422


@pytest.mark.parametrize("bins", [1, 50])
def test_distribution_bins_limits_accepted(client, viewer_h, dataset, bins):
    r = client.get(f"{BASE}/country/US/distribution", params={"bins": bins}, headers=viewer_h)
    assert r.status_code == 200 and len(r.json()["bins"]) == bins


# ---------- outliers ----------

def test_outliers_default_threshold(client, viewer_h, dataset):
    body = client.get(f"{BASE}/country/US/outliers", headers=viewer_h).json()
    assert body["threshold"] == 0.3 and body["currency"] == "USD"
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["salary"] == 160000.0 and item["job_title_median"] == 100000.0
    assert item["deviation"] == 0.6 and item["job_title"] == "Software Engineer"
    assert item["employee_code"] == f"ACME-{item['employee_id']:05d}"
    assert item["full_name"].count(" ") == 1


def test_outliers_ignore_terminated_when_computing_median_and_listing(client, viewer_h, dataset):
    items = client.get(f"{BASE}/country/US/outliers", headers=viewer_h).json()["items"]
    assert all(i["salary"] != 1_000_000 for i in items)


def test_outliers_threshold_is_strictly_greater_than(client, viewer_h, dataset):
    assert client.get(f"{BASE}/country/US/outliers", params={"threshold": 0.6}, headers=viewer_h).json()["items"] == []
    assert len(client.get(f"{BASE}/country/US/outliers", params={"threshold": 0.59}, headers=viewer_h).json()["items"]) == 1


def test_outliers_need_three_active_employees_in_title(client, viewer_h, make_employee):
    make_employee(country_code="US", salary=100, job_title="Account Executive", department="Sales")
    make_employee(country_code="US", salary=1000, job_title="Account Executive", department="Sales")
    assert client.get(f"{BASE}/country/US/outliers", headers=viewer_h).json()["items"] == []
    make_employee(country_code="US", salary=100, job_title="Account Executive", department="Sales")
    items = client.get(f"{BASE}/country/US/outliers", headers=viewer_h).json()["items"]
    assert [i["salary"] for i in items] == [1000.0]  # median is now 100 -> deviation 9.0


def test_outliers_sorted_by_abs_deviation_desc_then_id_and_signed(client, viewer_h, make_employee):
    for s in (100, 100, 100, 100, 170, 50, 50):
        make_employee(country_code="US", salary=s)
    # median of [50,50,100,100,100,100,170] = 100 ; devs: +0.7, -0.5, -0.5
    items = client.get(f"{BASE}/country/US/outliers", headers=viewer_h).json()["items"]
    assert [i["deviation"] for i in items] == [0.7, -0.5, -0.5]
    assert items[1]["employee_id"] < items[2]["employee_id"]


def test_outliers_compare_within_country_only(client, viewer_h, make_employee):
    for s in (100, 100, 100):
        make_employee(country_code="US", salary=s)
    for s in (5000, 5000, 5000):
        make_employee(country_code="IN", salary=s)
    assert client.get(f"{BASE}/country/US/outliers", headers=viewer_h).json()["items"] == []
    assert client.get(f"{BASE}/country/IN/outliers", headers=viewer_h).json()["items"] == []


def test_outliers_limit(client, viewer_h, make_employee):
    for s in [100] * 10 + [200, 300, 400]:
        make_employee(country_code="US", salary=s)
    items = client.get(f"{BASE}/country/US/outliers", params={"limit": 2}, headers=viewer_h).json()["items"]
    assert [i["salary"] for i in items] == [400.0, 300.0]


@pytest.mark.parametrize("params", [{"threshold": 0}, {"threshold": -0.1}, {"limit": 0}, {"limit": 201}])
def test_outliers_invalid_params_are_422(client, viewer_h, params):
    assert client.get(f"{BASE}/country/US/outliers", params=params, headers=viewer_h).status_code == 422


# ---------- unknown country ----------

@pytest.mark.parametrize("suffix", ["", "/distribution", "/outliers"])
def test_unknown_country_is_404(client, viewer_h, suffix):
    r = client.get(f"{BASE}/country/ZZ{suffix}", headers=viewer_h)
    assert r.status_code == 404 and "detail" in r.json()


def test_country_code_is_case_sensitive_or_normalised(client, viewer_h, dataset):
    r = client.get(f"{BASE}/country/us", headers=viewer_h)
    assert r.status_code in (200, 404)
