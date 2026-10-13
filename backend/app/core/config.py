from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), env_file_encoding="utf-8", extra="ignore")

    app_name: str = "CareerPilot"
    app_env: Literal["development", "test", "staging", "production"] = "development"
    api_prefix: str = "/api/v1"
    frontend_origin: str = "http://localhost:3000"
    log_level: str = "INFO"
    database_url: PostgresDsn | None = Field(default=None, repr=False)
    auth_secret: str | None = Field(default=None, repr=False)
    session_cookie_name: str = "careerpilot_session"
    session_cookie_secure: bool = False
    session_duration_hours: int = Field(default=168, gt=0, le=24 * 90)
    session_activity_update_minutes: int = Field(default=5, gt=0, le=60)
    auth_login_rate_limit: int = Field(default=10, gt=0, le=100)
    auth_rate_limit_window_seconds: int = Field(default=60, gt=0, le=3600)
    email_verification_ttl_hours: int = Field(default=24, gt=0, le=24 * 14)
    password_reset_ttl_minutes: int = Field(default=30, gt=0, le=24 * 60)
    google_client_id: str | None = None
    google_client_secret: str | None = Field(default=None, repr=False)
    github_client_id: str | None = None
    github_client_secret: str | None = Field(default=None, repr=False)
    linkedin_client_id: str | None = None
    linkedin_client_secret: str | None = Field(default=None, repr=False)
    backend_origin: str = "http://localhost:8000"
    recent_auth_minutes: int = Field(default=10, ge=1, le=30)
    email_provider: Literal["", "smtp", "resend"] = ""
    email_from: str | None = None
    email_api_key: str | None = Field(default=None, repr=False)
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = Field(default=None, repr=False)
    smtp_password: str | None = Field(default=None, repr=False)
    smtp_tls: Literal["starttls", "ssl"] = "starttls"
    email_failover_provider: Literal["", "smtp", "resend"] = ""
    email_max_attempts: int = Field(default=4, ge=1, le=6)
    email_provider_per_minute: int = Field(default=60, ge=1, le=1000)
    email_provider_per_second: int = Field(default=2, ge=1, le=50)
    redis_url: str = Field(default="redis://localhost:6379/0", repr=False)
    database_host_override: str | None = None
    docs_enabled: bool = True
    job_source_config: str = ""
    job_freshness_hours: int = Field(default=72, ge=1, le=720)

    @field_validator("job_source_config")
    @classmethod
    def supported_job_sources(cls, value: str) -> str:
        value = value.strip()
        if value not in {"", "arbeitnow"}:
            raise ValueError("JOB_SOURCE_CONFIG must be blank or arbeitnow.")
        return value

    @field_validator("frontend_origin")
    @classmethod
    def no_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def sqlalchemy_database_url(self) -> str | None:
        """Return the validated database URL in the string form SQLAlchemy expects."""
        if not self.database_url:
            return None
        from sqlalchemy.engine import make_url
        url = make_url(str(self.database_url))
        if self.database_host_override:
            url = url.set(host=self.database_host_override)
        return url.render_as_string(hide_password=False)


@lru_cache
def get_settings() -> Settings:
    return Settings()
