from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.core.enums import EmployeeStatus, EmploymentType, Role
from app.core.reference import COUNTRIES, DEPARTMENTS, JOB_TITLES

router = APIRouter(tags=["meta"], dependencies=[Depends(get_current_user)])


@router.get("/meta")
def get_meta() -> dict:
    return {
        "countries": [
            {"code": code, "name": c["name"], "currency": c["currency"]}
            for code, c in COUNTRIES.items()
        ],
        "departments": DEPARTMENTS,
        "job_titles": JOB_TITLES,
        "employment_types": [e.value for e in EmploymentType],
        "statuses": [s.value for s in EmployeeStatus],
        "roles": [r.value for r in Role],
    }
