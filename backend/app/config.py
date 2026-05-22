"""Application settings, loaded once from environment variables."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = Field(..., description="Async SQLAlchemy URL (asyncpg driver).")
    database_url_sync: str = Field(..., description="Sync URL used by alembic.")

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Supabase JWT verification
    supabase_project_ref: str = ""
    supabase_jwks_url: str = ""
    supabase_jwt_secret: str = ""

    # Crypto pepper for API key HMAC
    api_key_pepper: str = Field(..., min_length=32, description="Hex-encoded pepper, ≥16 bytes.")

    # App
    frontend_origin: str = "http://localhost:5173"
    cors_allowed_origins: str = ""
    webhook_http_timeout_seconds: float = 10.0
    webhook_max_attempts: int = 6
    log_level: str = "INFO"

    # Per-API-key rate limiting (fixed-window, 1 minute).
    rate_limit_per_minute: int = 120
    # Reserved for future token-bucket upgrade; not consumed by the
    # current fixed-window implementation.
    rate_limit_burst: int = 60

    @field_validator("api_key_pepper")
    @classmethod
    def _pepper_is_hex(cls, v: str) -> str:
        try:
            raw = bytes.fromhex(v)
        except ValueError as e:
            raise ValueError("API_KEY_PEPPER must be hex-encoded") from e
        if len(raw) < 16:
            raise ValueError("API_KEY_PEPPER must decode to at least 16 bytes")
        return v

    @property
    def api_key_pepper_bytes(self) -> bytes:
        return bytes.fromhex(self.api_key_pepper)

    @property
    def cors_origins(self) -> list[str]:
        """Resolve allowed CORS origins.

        Reads `CORS_ALLOWED_ORIGINS` (comma-separated). Falls back to
        `FRONTEND_ORIGIN` if unset. Use `*` to allow any origin.
        """
        raw = (self.cors_allowed_origins or self.frontend_origin or "").strip()
        if not raw:
            return []
        return [o.strip() for o in raw.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
