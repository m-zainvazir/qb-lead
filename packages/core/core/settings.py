"""One settings module for every Python service.

Values come from the environment (or a local `.env`). A missing required value
fails at startup, never halfway through a request. Settings never live in code.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- required -----------------------------------------------------------
    app_env: Literal["local", "test", "staging", "production"]
    supabase_url: str
    supabase_anon_key: SecretStr
    database_url_api: SecretStr
    database_url_system: SecretStr
    redis_url: SecretStr

    # --- optional, safe defaults ----------------------------------------------
    log_level: str = "INFO"
    git_commit: str = "dev"
    web_base_url: str = "http://localhost:3000"
    supabase_jwt_secret: SecretStr | None = None
    supabase_service_role_key: SecretStr | None = None
    database_url_admin: SecretStr | None = None  # migrations, db-roles, tests only
    app_db_password: SecretStr | None = None  # read only by `api.cli db-roles`
    system_db_password: SecretStr | None = None
    supabase_jwt_issuer: str | None = None  # set when the API reaches Supabase on another host
    jwt_audience: str = "authenticated"
    jwks_cache_seconds: int = Field(default=600, ge=30)
    db_pool_min: int = Field(default=1, ge=0)
    db_pool_max: int = Field(default=10, ge=1)
    db_statement_timeout_ms: int = Field(default=15_000, ge=100)
    embedding_provider: Literal["fastembed", "hash"] = "fastembed"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_cache_dir: str | None = None
    embedding_cost_per_1k_chars: float = Field(default=0.0, ge=0)
    storage_bucket: str = "portfolio"
    smtp_host: str = "127.0.0.1"
    smtp_port: int = 54325
    smtp_from: str = "no-reply@leadgen.local"

    @property
    def jwt_issuer(self) -> str:
        return self.supabase_jwt_issuer or f"{self.supabase_url.rstrip('/')}/auth/v1"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def refuse_in_production(action: str) -> None:
    """Guard for resets, seeding and test helpers (CLAUDE.md: never against production)."""
    if get_settings().is_production:
        raise SystemExit(f"Refusing to {action}: APP_ENV is production.")
