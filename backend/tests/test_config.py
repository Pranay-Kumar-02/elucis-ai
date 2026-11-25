from __future__ import annotations

import pytest
from pydantic import ValidationError

from tests.conftest import make_settings


def test_defaults_are_local_and_safe() -> None:
    s = make_settings()
    assert s.ollama_chat_model == "qwen3:4b"
    assert s.ollama_embed_model == "qwen3-embedding:0.6b"
    assert s.embedding_dimension == 1024
    assert s.api_cors_origins == ["http://localhost:5173", "http://127.0.0.1:5173"]
    assert s.diagnostics_enabled is True


def test_cors_origins_parse_from_comma_separated_string() -> None:
    s = make_settings(api_cors_origins="http://localhost:5173, http://localhost:4173")
    assert s.api_cors_origins == ["http://localhost:5173", "http://localhost:4173"]


@pytest.mark.parametrize("origin", ["*", "localhost:5173", "http://localhost:5173/app", "ftp://x"])
def test_invalid_cors_origins_rejected(origin: str) -> None:
    with pytest.raises(ValidationError):
        make_settings(api_cors_origins=origin)


def test_production_refuses_dev_endpoints() -> None:
    with pytest.raises(ValidationError, match="ENABLE_DEV_ENDPOINTS"):
        make_settings(app_env="production", enable_dev_endpoints=True)


def test_production_requires_secrets() -> None:
    with pytest.raises(ValidationError, match="session_secret"):
        make_settings(
            app_env="production",
            enable_dev_endpoints=False,
            database_url="postgresql://u:p@localhost/db",
        )


def test_production_hides_diagnostics_by_default() -> None:
    s = make_settings(
        app_env="production",
        enable_dev_endpoints=False,
        database_url="postgresql://u:p@localhost/db",
        session_secret="x" * 32,
        app_encryption_key="y" * 32,
    )
    assert s.diagnostics_enabled is False


def test_secrets_never_in_repr_and_dsn_redacted() -> None:
    s = make_settings(database_url="postgresql://app_api:s3cret-pw@localhost:5432/elucis_dev")
    assert "s3cret-pw" not in repr(s)
    assert s.dsn_redacted() == "postgresql://app_api:***@localhost:5432/elucis_dev"
    assert s.dsn() == "postgresql://app_api:s3cret-pw@localhost:5432/elucis_dev"


def test_worker_and_migration_urls_fall_back_to_api_url() -> None:
    s = make_settings(database_url="postgresql://a:b@h/d")
    assert s.dsn("worker") == s.dsn("migration") == "postgresql://a:b@h/d"


def test_unknown_log_level_rejected() -> None:
    with pytest.raises(ValidationError):
        make_settings(log_level="LOUD")
