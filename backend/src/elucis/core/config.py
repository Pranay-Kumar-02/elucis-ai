"""Environment-based application settings.

All configuration comes from environment variables, optionally loaded from the repository's
``.env`` file (git-ignored). ``.env.example`` documents every name. Secrets are held as
``SecretStr`` so they never appear in ``repr()``, logs or error pages.
"""

from __future__ import annotations

import base64
import binascii
import re
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Self
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# backend/src/elucis/core/config.py -> repository root is four levels up.
REPO_ROOT = Path(__file__).resolve().parents[4]
BACKEND_ROOT = REPO_ROOT / "backend"


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class LogFormat(StrEnum):
    JSON = "json"
    CONSOLE = "console"


def _redact_dsn(url: str) -> str:
    """Return a database URL with the password replaced, safe for logs and reports."""
    parts = urlsplit(url)
    if parts.password is None:
        return url
    netloc = parts.netloc.replace(f":{parts.password}@", ":***@", 1)
    return parts._replace(netloc=netloc).geturl()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env",),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        # A rejected value is often a secret (a key, a URL with a password): never echo it.
        hide_input_in_errors=True,
    )

    # ---- application ----
    app_env: Environment = Environment.DEVELOPMENT
    app_name: str = "Elucis AI"
    log_level: str = "INFO"
    log_format: LogFormat = LogFormat.CONSOLE

    # ---- HTTP ----
    api_cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )
    api_max_body_bytes: int = 1 * 1024 * 1024  # D09 section 1: request body <= 1 MB
    upload_max_bytes: int = 20 * 1024 * 1024  # A-06: uploads <= 20 MB
    expose_diagnostics: bool | None = None  # None -> True outside production
    enable_dev_endpoints: bool = False

    # ---- database (three roles, D07 section 5) ----
    database_url: SecretStr | None = None  # app_api
    database_worker_url: SecretStr | None = None  # app_worker; falls back to database_url
    database_migration_url: SecretStr | None = None  # app_owner; falls back to database_url
    database_pool_size: int = Field(default=5, ge=1, le=50)
    database_max_overflow: int = Field(default=5, ge=0, le=50)
    database_connect_timeout_s: int = Field(default=5, ge=1, le=60)
    database_statement_timeout_ms: int = Field(default=30_000, ge=100)

    # ---- model runtime ----
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_chat_model: str = "qwen3:4b"
    ollama_embed_model: str = "qwen3-embedding:0.6b"
    ollama_timeout_s: float = Field(default=180.0, gt=0)
    ollama_num_ctx: int = Field(default=4096, ge=512)
    embedding_dimension: int = Field(default=1024, ge=1)  # D07 assumption, measured by EXP-04

    # ---- optional cloud backup for chat calls (IMP-38); off unless a workspace enables it ----
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.5-flash-lite"
    gemini_timeout_s: float = Field(default=60.0, gt=0)

    @property
    def gemini_configured(self) -> bool:
        return self.gemini_api_key is not None and bool(self.gemini_api_key.get_secret_value())

    # ---- ingestion ----
    upload_dir: Path = REPO_ROOT / "data" / "uploads"
    preview_rows: int = Field(default=20, ge=1, le=200)

    # ---- worker ----
    worker_poll_interval_s: float = Field(default=2.0, gt=0)
    worker_heartbeat_interval_s: float = Field(default=15.0, gt=0)

    # ---- sessions (D09 section 1, D10 section 2) ----
    session_idle_minutes: int = Field(default=30, ge=1)  # A-07
    session_absolute_hours: int = Field(default=12, ge=1)  # D10 proposal
    session_cookie_secure: bool | None = None  # None -> True in production (HTTPS)

    # ---- secrets used by later modules (SEC-18) ----
    session_secret: SecretStr | None = None
    app_encryption_key: SecretStr | None = None
    customer_key_secret: SecretStr | None = None

    @field_validator("api_cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("api_cors_origins")
    @classmethod
    def _check_origins(cls, value: list[str]) -> list[str]:
        for origin in value:
            if origin == "*":
                raise ValueError("Wildcard CORS origin is not allowed (credentials are used)")
            parts = urlsplit(origin)
            if parts.scheme not in {"http", "https"} or not parts.netloc or parts.path:
                raise ValueError(f"Invalid CORS origin {origin!r}: use scheme://host[:port]")
        return value

    @field_validator("app_encryption_key")
    @classmethod
    def _check_fernet_key(cls, value: SecretStr | None) -> SecretStr | None:
        """Fail at startup, never at first use, when the key cannot work (AGR-16)."""
        if value is not None and not is_fernet_key(value.get_secret_value()):
            raise ValueError(FERNET_KEY_HELP)
        return value

    @field_validator("log_level")
    @classmethod
    def _check_level(cls, value: str) -> str:
        level = value.upper()
        if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError(f"Unknown log level {value!r}")
        return level

    @model_validator(mode="after")
    def _production_guards(self) -> Self:
        if self.app_env is Environment.PRODUCTION:
            if self.enable_dev_endpoints:
                raise ValueError("ENABLE_DEV_ENDPOINTS must be false in production")
            missing = [
                name
                for name in ("database_url", "session_secret", "app_encryption_key")
                if getattr(self, name) is None
            ]
            if missing:
                raise ValueError(f"Missing required production settings: {', '.join(missing)}")
        return self

    # ---- derived values ----
    @property
    def is_production(self) -> bool:
        return self.app_env is Environment.PRODUCTION

    @property
    def cookie_secure(self) -> bool:
        if self.session_cookie_secure is None:
            return self.is_production
        return self.session_cookie_secure

    @property
    def diagnostics_enabled(self) -> bool:
        if self.expose_diagnostics is None:
            return not self.is_production
        return self.expose_diagnostics

    def dsn(self, role: str = "api") -> str | None:
        """Return the raw database URL for ``api``, ``worker`` or ``migration``."""
        chosen = {
            "api": self.database_url,
            "worker": self.database_worker_url or self.database_url,
            "migration": self.database_migration_url or self.database_url,
        }[role]
        return chosen.get_secret_value() if chosen else None

    def dsn_redacted(self, role: str = "api") -> str | None:
        raw = self.dsn(role)
        return _redact_dsn(raw) if raw else None


FERNET_KEY_HELP = (
    "APP_ENCRYPTION_KEY is not a valid Fernet key. It must be 32 random bytes in URL-safe"
    " base64 (44 characters, ending in '='). Run scripts/windows/20-setup-project.ps1 to"
    ' replace it, or generate one with: python -c "import base64, os;'
    ' print(base64.urlsafe_b64encode(os.urandom(32)).decode())"'
)


_FERNET_KEY_SHAPE = re.compile(r"[A-Za-z0-9_-]{43}=")  # URL-safe alphabet only


def is_fernet_key(value: str) -> bool:
    """A Fernet key: 32 bytes, URL-safe base64 with padding (44 characters)."""
    if not _FERNET_KEY_SHAPE.fullmatch(value):
        return False
    try:
        return len(base64.urlsafe_b64decode(value)) == 32
    except (binascii.Error, ValueError):
        return False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
