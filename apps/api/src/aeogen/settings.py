"""Settings parity for apps/web's @t3-oss/env-nextjs.

Validates env vars at startup. Like A.T4's src/lib/env.ts, this only
declares fields that exist today — Supabase / OpenRouter / DB fields
are added in A.T8/T9 alongside their first real consumers.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Top-level application settings. Loaded from env + .env.local."""

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: Literal["development", "test", "staging", "production"] = Field(
        default="development",
        description="Deployment environment.",
    )
    app_name: str = Field(default="aeogen-api")
    app_version: str = Field(default="0.0.0")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")

    # Server
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=8000, ge=1, le=65535)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor for DI use."""
    return Settings()
