# FILE: tests/body/cli/commands/test_secrets.py


import pytest


pytestmark = pytest.mark.legacy

from dataclasses import dataclass, field
from datetime import datetime
from types import SimpleNamespace
from typing import Any

from typer.testing import CliRunner

from body.cli.commands import secrets as secrets_cli
from shared.exceptions import SecretNotFoundError


runner = CliRunner()


# ---------------------------------------------------------------------------
# In-memory backend used only in tests
# ---------------------------------------------------------------------------


@dataclass
class InMemorySecretRecord:
    value: str
    description: str | None
    last_updated: datetime = field(default_factory=datetime.utcnow)


class InMemorySecretsService:
    """
    Simple in-memory implementation of the secrets service interface used by the CLI.
    """

    def __init__(self) -> None:
        self._data: dict[str, InMemorySecretRecord] = {}

    async def get_secret(self, db: Any, key: str, audit_context: str) -> str:
        try:
            return self._data[key].value
        except KeyError:
            raise SecretNotFoundError(f"Secret '{key}' not found")

    async def set_secret(
        self,
        db: Any,
        key: str,
        value: str,
        description: str | None,
        audit_context: str,
    ) -> None:
        self._data[key] = InMemorySecretRecord(
            value=value,
            description=description,
        )

    async def delete_secret(self, db: Any, key: str) -> None:
        if key not in self._data:
            raise SecretNotFoundError(f"Secret '{key}' not found")
        del self._data[key]

    async def list_secrets(self, db: Any) -> list[dict[str, Any]]:
        return [
            {
                "key": key,
                "description": rec.description,
                "last_updated": rec.last_updated,
            }
            for key, rec in self._data.items()
        ]


class DummyAsyncSession:
    """
    Minimal async context manager to stand in for a DB session.
    """

    async def __aenter__(self) -> Any:
        return SimpleNamespace()

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


@pytest.fixture()
def fake_secrets_env(monkeypatch):
    """
    Patch:
    - get_session          → in-memory async session
    - get_secrets_service  → single in-memory service instance
    - confirm_action       → non-interactive (always True by default)

    Returns the in-memory service so tests can inspect internal state if needed.
    """

    service = InMemorySecretsService()

    # MUST be a *sync* function returning an async context manager
    def fake_get_session():
        return DummyAsyncSession()

    async def fake_get_secrets_service(db):
        return service

    def fake_confirm_action(*args, **kwargs) -> bool:
        return True

    monkeypatch.setattr(secrets_cli, "get_session", fake_get_session, raising=True)
    monkeypatch.setattr(
        secrets_cli,
        "get_secrets_service",
        fake_get_secrets_service,
        raising=True,
    )
    monkeypatch.setattr(
        secrets_cli,
        "confirm_action",
        fake_confirm_action,
        raising=True,
    )

    return service


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_secrets_full_lifecycle(fake_secrets_env):
    """
    Full happy-path lifecycle:
    - set secret
    - get secret (exists)
    - list secrets
    - delete secret
    - get secret again → should fail with exit_code != 0
    """

    # 1) set
    result_set = runner.invoke(
        secrets_cli.app,
        [
            "set",
            "test.api_key",
            "--value",
            "supersecret",
            "--description",
            "Test secret",
        ],
    )
    assert result_set.exit_code == 0, result_set.stdout
    assert "Secret 'test.api_key' stored successfully" in result_set.stdout

    # 2) get (exists)
    result_get = runner.invoke(
        secrets_cli.app,
        ["get", "test.api_key", "--show"],
    )
    assert result_get.exit_code == 0, result_get.stdout
    assert "Secret 'test.api_key':" in result_get.stdout
    assert "supersecret" in result_get.stdout

    # 3) list
    result_list = runner.invoke(secrets_cli.app, ["list"])
    assert result_list.exit_code == 0, result_list.stdout
    assert "Encrypted Secrets" in result_list.stdout
    assert "test.api_key" in result_list.stdout

    # 4) delete
    result_delete = runner.invoke(
        secrets_cli.app,
        ["delete", "test.api_key", "--yes"],
    )
    assert result_delete.exit_code == 0, result_delete.stdout
    assert "Secret 'test.api_key' deleted" in result_delete.stdout

    # 5) get again → should *not* succeed
    result_get_missing = runner.invoke(
        secrets_cli.app,
        ["get", "test.api_key"],
    )
    assert result_get_missing.exit_code != 0
    assert "Secret 'test.api_key' not found" in result_get_missing.stdout


def test_set_secret_requires_overwrite_confirmation(fake_secrets_env, monkeypatch):
    """
    If a secret already exists and user refuses to overwrite, set should not change it.
    """

    service = fake_secrets_env

    # Seed existing secret directly into in-memory backend
    service._data["test.api_key"] = InMemorySecretRecord(
        value="original",
        description="Original secret",
    )

    # Simulate user refusing overwrite
    def confirm_no(message, abort_message=""):
        if abort_message:
            print(abort_message)
        return False

    monkeypatch.setattr(secrets_cli, "confirm_action", confirm_no, raising=True)

    # Run set without --force
    result = runner.invoke(
        secrets_cli.app,
        ["set", "test.api_key", "--value", "newvalue"],
    )

    # CLI should exit successfully (overwrite cancelled, not an error)
    assert result.exit_code == 0, result.stdout
    assert "Overwrite cancelled" in result.stdout

    # Secret value must remain unchanged
    assert service._data["test.api_key"].value == "original"


def test_get_secret_not_found(fake_secrets_env):
    """
    Getting a non-existent secret should return an error exit code and proper message.
    """

    result = runner.invoke(
        secrets_cli.app,
        ["get", "missing.secret"],
    )

    assert result.exit_code != 0
    assert "Secret 'missing.secret' not found" in result.stdout
