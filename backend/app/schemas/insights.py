from pydantic import BaseModel


class Summary(BaseModel):
    headcount: int
    min: float | None
    p25: float | None
    median: float | None
    p75: float | None
    max: float | None
    mean: float | None
    total_payroll: float | None


class CountryOverview(BaseModel):
    country_code: str
    currency: str
    headcount: int
    median_salary: float | None
    mean_salary: float | None


class DepartmentCount(BaseModel):
    department: str
    headcount: int


class EmploymentTypeCount(BaseModel):
    employment_type: str
    headcount: int


class Overview(BaseModel):
    total_headcount: int
    by_country: list[CountryOverview]
    by_department: list[DepartmentCount]
    by_employment_type: list[EmploymentTypeCount]


class DepartmentSummary(BaseModel):
    department: str
    summary: Summary


class JobTitleSummary(BaseModel):
    job_title: str
    summary: Summary


class CountryInsights(BaseModel):
    country_code: str
    currency: str
    summary: Summary
    by_department: list[DepartmentSummary]
    by_job_title: list[JobTitleSummary]


class Bin(BaseModel):
    lower: float
    upper: float
    count: int


class Distribution(BaseModel):
    country_code: str
    currency: str
    bins: list[Bin]


class Outlier(BaseModel):
    employee_id: int
    employee_code: str
    full_name: str
    job_title: str
    salary: float
    job_title_median: float
    deviation: float


class Outliers(BaseModel):
    country_code: str
    currency: str
    threshold: float
    items: list[Outlier]
