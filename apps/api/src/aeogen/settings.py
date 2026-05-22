"""Settings parity for apps/web's @t3-oss/env-nextjs.

Validates env vars at startup. Supabase fields land in A.T8; OpenRouter /
Redis / DATABASE_URL follow in A.T9 alongside their first real consumers.
"""

from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, HttpUrl, PostgresDsn, SecretStr, field_validator
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

    # Supabase (A.T8). New-format keys only; legacy JWT keys rejected.
    supabase_url: HttpUrl = Field(
        description="e.g. https://ngjlxlkdfgfhiookndpl.supabase.co",
    )
    supabase_publishable_key: str = Field(
        pattern=r"^sb_publishable_",
        min_length=20,
        description="New-format publishable key (sb_publishable_...).",
    )
    supabase_secret_key: SecretStr = Field(
        description="New-format secret key (sb_secret_...). SecretStr blocks repr leak.",
    )

    @field_validator("supabase_secret_key")
    @classmethod
    def _validate_secret_prefix(cls, v: SecretStr) -> SecretStr:
        if not v.get_secret_value().startswith("sb_secret_"):
            raise ValueError("must be a new-format Supabase secret key (sb_secret_...)")
        return v

    # Postgres direct connection (C.2). Required by AsyncPostgresSaver.
    # NOT the Supabase API URL — that lives in `supabase_url` above.
    database_url: PostgresDsn = Field(
        ...,
        validation_alias=AliasChoices("DATABASE_URL"),
        description=(
            "Direct Postgres connection string for AsyncPostgresSaver. "
            "Use Supabase Session pooler (port 5432), not Transaction pooler (6543) — "
            "LangGraph relies on BEGIN/SAVEPOINT which Transaction mode silently breaks."
        ),
        repr=False,
    )

    # OpenRouter (C.3). OPENROUTER_API_KEY is required; no prefix validator
    # because OpenRouter keys don't follow a stable format.
    openrouter_api_key: SecretStr = Field(
        description="OpenRouter API key (sk-or-v1-... or any format).",
    )
    openrouter_base_url: HttpUrl = Field(
        default="https://openrouter.ai/api/v1",  # type: ignore[assignment]
        description="OpenRouter-compatible OpenAI API base URL.",
    )
    openrouter_default_model: str = Field(
        default="anthropic/claude-sonnet-4.5",
        description="Default model for agent LLM calls via OpenRouter.",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor for DI use.

    pydantic-settings populates required fields from environment variables at
    runtime, but mypy can't see that — silence the false-positive call-arg.
    """
    return Settings()  # type: ignore[call-arg]
