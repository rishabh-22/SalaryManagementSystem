"""Reference data: countries, departments, job titles and seed salary ranges."""

COUNTRIES: dict[str, dict[str, str]] = {
    "US": {"name": "United States", "currency": "USD"},
    "GB": {"name": "United Kingdom", "currency": "GBP"},
    "IN": {"name": "India", "currency": "INR"},
    "DE": {"name": "Germany", "currency": "EUR"},
    "CA": {"name": "Canada", "currency": "CAD"},
    "SG": {"name": "Singapore", "currency": "SGD"},
    "AU": {"name": "Australia", "currency": "AUD"},
    "BR": {"name": "Brazil", "currency": "BRL"},
}

DEPARTMENTS: list[str] = [
    "Engineering",
    "Product",
    "Design",
    "Sales",
    "Marketing",
    "Finance",
    "HR",
    "Operations",
    "Customer Support",
    "Legal",
]

# job title -> (department, base annual salary in USD terms)
_TITLE_BASE: dict[str, tuple[str, float]] = {
    "Software Engineer": ("Engineering", 110_000),
    "Senior Software Engineer": ("Engineering", 145_000),
    "Engineering Manager": ("Engineering", 175_000),
    "Data Analyst": ("Engineering", 85_000),
    "Product Manager": ("Product", 130_000),
    "Product Designer": ("Design", 95_000),
    "UX Researcher": ("Design", 90_000),
    "Sales Representative": ("Sales", 70_000),
    "Account Executive": ("Sales", 95_000),
    "Marketing Specialist": ("Marketing", 68_000),
    "Marketing Manager": ("Marketing", 105_000),
    "Financial Analyst": ("Finance", 80_000),
    "Accountant": ("Finance", 72_000),
    "HR Specialist": ("HR", 65_000),
    "Recruiter": ("HR", 67_000),
    "Operations Analyst": ("Operations", 70_000),
    "Operations Manager": ("Operations", 100_000),
    "Customer Support Agent": ("Customer Support", 42_000),
    "Support Team Lead": ("Customer Support", 62_000),
    "Legal Counsel": ("Legal", 140_000),
}

JOB_TITLES: list[str] = list(_TITLE_BASE)
TITLE_DEPARTMENT: dict[str, str] = {t: d for t, (d, _) in _TITLE_BASE.items()}

# Rough local-currency multiplier relative to the USD base (not an FX service;
# only used to generate plausible seed data).
COUNTRY_SALARY_FACTOR: dict[str, float] = {
    "US": 1.0,
    "GB": 0.78,
    "IN": 28.0,
    "DE": 0.85,
    "CA": 1.25,
    "SG": 1.2,
    "AU": 1.3,
    "BR": 3.2,
}


def base_salary(job_title: str, country_code: str) -> float:
    """Typical (median) annual salary for a title in a country's local currency."""
    return _TITLE_BASE[job_title][1] * COUNTRY_SALARY_FACTOR[country_code]


def currency_for(country_code: str) -> str:
    return COUNTRIES[country_code]["currency"]
