import os

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "sqlite:///./salary.db"
    # Dev-only default; compose requires an explicit value.
    JWT_SECRET: str = "dev-only-insecure-secret-change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    # Comma-separated list of allowed origins.
    CORS_ORIGINS: str = "http://localhost:5173"

    @field_validator("JWT_SECRET")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        # Only enforce secure JWT_SECRET in production environments.
        is_production = os.getenv("ENV") == "production" or os.getenv("ENVIRONMENT") == "production"
        if is_production and v == "dev-only-insecure-secret-change-me-in-production":
            raise ValueError("JWT_SECRET must be set to a secure value in production")
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
