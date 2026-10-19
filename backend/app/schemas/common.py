from datetime import UTC, datetime
from typing import Annotated

from pydantic import AfterValidator, Field, PlainSerializer, StringConstraints

from app.core.reference import COUNTRIES, DEPARTMENTS, JOB_TITLES


def _as_utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


# Stored as naive UTC; always emitted as ISO 8601 with a trailing Z.
UTCDatetime = Annotated[datetime, PlainSerializer(_as_utc_iso, return_type=str)]

# Light-weight email check (avoids the email-validator dependency).
Email = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_lower=True,
        max_length=255,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    ),
]

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


def _round_salary(value: float) -> float:
    rounded = round(value, 2)
    if rounded <= 0:
        raise ValueError("salary must be greater than 0")
    if rounded > 1e7:
        raise ValueError("salary must not exceed 10,000,000")
    return rounded


Salary = Annotated[float, Field(gt=0, le=1e7, allow_inf_nan=False), AfterValidator(_round_salary)]


def _in_choices(choices: set[str] | list[str], label: str) -> AfterValidator:
    def check(value: str) -> str:
        if value not in choices:
            raise ValueError(f"unknown {label}: {value}")
        return value

    return AfterValidator(check)


CountryCode = Annotated[str, _in_choices(set(COUNTRIES), "country code")]
Department = Annotated[str, _in_choices(DEPARTMENTS, "department")]
JobTitle = Annotated[str, _in_choices(JOB_TITLES, "job title")]
