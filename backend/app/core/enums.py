from enum import StrEnum


class Role(StrEnum):
    ADMIN = "admin"
    HR_MANAGER = "hr_manager"
    VIEWER = "viewer"


class EmploymentType(StrEnum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"


class EmployeeStatus(StrEnum):
    ACTIVE = "active"
    TERMINATED = "terminated"
