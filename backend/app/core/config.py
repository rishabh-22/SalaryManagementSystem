import os
from typing import Literal
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parents[2]
_DEFAULT_DATABASE_PATH = _BACKEND_DIR / "salary.db"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_BACKEND_DIR / ".env", extra="ignore")

    DATABASE_URL: str = f"sqlite:///{_DEFAULT_DATABASE_PATH}"
    # Dev-only default; compose requires an explicit value.
    JWT_SECRET: str = "dev-only-insecure-secret-change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    # Comma-separated list of allowed origins.
    CORS_ORIGINS: str = "http://localhost:5173"

    # Chat assistant. AGENT_PROVIDER picks the provider; an unsupported value fails startup.
    # Empty, or an empty key for the selected provider, disables /api/chat (503); the rest of the
    # app is unaffected.
    AGENT_PROVIDER: Literal["", "openai", "anthropic", "gemini"] = ""
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-haiku-5-5"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    CHAT_MAX_TOKENS: int = 1024
    CHAT_MAX_TOOL_ITERATIONS: int = 6

    @field_validator("AGENT_PROVIDER", mode="before")
    @classmethod
    def normalise_agent_provider(cls, v: object) -> object:
        return v.strip().lower() if isinstance(v, str) else v

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
