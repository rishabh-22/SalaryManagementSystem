# ruff: noqa: E501
from app.core import reference

EXPECTED = {
    "US": "USD", "GB": "GBP", "IN": "INR", "DE": "EUR",
    "CA": "CAD", "SG": "SGD", "AU": "AUD", "BR": "BRL",
}


def _currency(info):
    return info["currency"] if isinstance(info, dict) else info.currency


def test_countries_map_to_expected_currency():
    assert {c: _currency(i) for c, i in reference.COUNTRIES.items()} == EXPECTED


def test_departments_are_the_contracted_ten():
    assert set(reference.DEPARTMENTS) == {
        "Engineering", "Product", "Design", "Sales", "Marketing",
        "Finance", "HR", "Operations", "Customer Support", "Legal",
    }


def test_job_titles_non_empty_and_unique():
    titles = list(reference.JOB_TITLES)
    assert titles and len(titles) == len(set(titles))
    assert "Software Engineer" in titles
