# tests/cli/test_admin_cli__readonly.py
"""`core-admin --readonly` runs on the read-only login, every transaction read-only.

The login file's DATABASE_URL replaces whatever .env or the secrets file gave,
so a read-only run can never fall back to a login that writes; without the
file the command refuses instead of running on the normal login.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import typer

from cli import admin_cli
from cli.utils.exit_codes import EXIT_CONFIG_ERROR
from shared.config import settings
from shared.infrastructure.database import session_manager


@pytest.fixture
def clean_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql+asyncpg://writer@h/db")
    monkeypatch.setattr(settings, "DATABASE_READ_ONLY", False)
    monkeypatch.setattr(settings, "QDRANT_URL", None)


# ID: e97c8d86-19ed-4307-a964-aefc24afccc9
def test_readonly_login_replaces_the_configured_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clean_settings: None
) -> None:
    env = tmp_path / "readonly.env"
    env.write_text(
        "DATABASE_URL=postgresql+asyncpg://reader:pw@h/db\n"
        "QDRANT_URL=http://127.0.0.1:6333\n"
    )
    monkeypatch.setenv("CORE_READONLY_ENV", str(env))

    admin_cli._use_readonly_login()

    assert settings.DATABASE_URL == "postgresql+asyncpg://reader:pw@h/db"
    assert settings.DATABASE_READ_ONLY is True
    assert settings.QDRANT_URL == "http://127.0.0.1:6333"


# ID: 23a28ffc-6d50-4588-9fd1-a29e6f191018
def test_readonly_without_login_file_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clean_settings: None
) -> None:
    monkeypatch.setenv("CORE_READONLY_ENV", str(tmp_path / "missing.env"))

    with pytest.raises(typer.Exit) as exc:
        admin_cli._use_readonly_login()

    assert exc.value.exit_code == EXIT_CONFIG_ERROR
    assert settings.DATABASE_URL == "postgresql+asyncpg://writer@h/db"
    assert settings.DATABASE_READ_ONLY is False


# ID: e8703614-7893-4853-821e-f06e151eabff
@pytest.mark.parametrize(
    ("read_only", "expected"),
    [
        (True, {"server_settings": {"default_transaction_read_only": "on"}}),
        (False, {}),
    ],
)
def test_engine_opens_read_only_transactions_when_asked(
    monkeypatch: pytest.MonkeyPatch,
    clean_settings: None,
    read_only: bool,
    expected: dict,
) -> None:
    seen: dict = {}

    def _fake_engine(url: str, **kwargs: object) -> object:
        seen.update(kwargs)
        return object()

    monkeypatch.setattr(settings, "DATABASE_READ_ONLY", read_only)
    monkeypatch.setattr(session_manager, "create_async_engine", _fake_engine)
    monkeypatch.setattr(session_manager, "async_sessionmaker", lambda **_: None)

    session_manager._create_state()

    assert seen["connect_args"] == expected
