from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

from app.core.enums import Role
from app.schemas.common import Email, UTCDatetime

Password = Annotated[str, StringConstraints(min_length=8, max_length=72)]
FullName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    role: Role
    is_active: bool
    created_at: UTCDatetime


class UserCreate(BaseModel):
    email: Email
    full_name: FullName
    password: Password
    role: Role


class UserUpdate(BaseModel):
    full_name: FullName | None = None
    role: Role | None = None
    is_active: bool | None = None
    password: Password | None = None

    @model_validator(mode="after")
    def _no_explicit_nulls(self) -> "UserUpdate":
        for name in self.model_fields_set:
            if getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
