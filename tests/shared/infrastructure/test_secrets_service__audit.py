# tests/shared/infrastructure/test_secrets_service__audit.py
"""Secret-access audit trail: every access leaves a durable row.

Before the fix, read paths never committed (the audit row was discarded when
the session closed) and any non-role context ("cli:get", "api:set",
"rotation") failed the cognitive_role FK, which also aborted the caller's
transaction, so an overwrite after an existence check failed.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import text

from shared.infrastructure.database.session_manager import get_session
from shared.infrastructure.secrets_service import SecretsService


async def _audit_rows(key: str) -> list[tuple[str | None, str | None, str]]:
    async with get_session() as fresh:
        result = await fresh.execute(
            text(
                "SELECT cognitive_role, resource_name, content "
                "FROM core.agent_memory WHERE content LIKE :pattern "
                "ORDER BY created_at, id"
            ),
            {"pattern": f"% secret: {key}"},
        )
        return [tuple(r) for r in result.fetchall()]


@pytest.fixture
def service() -> SecretsService:
    return SecretsService(Fernet.generate_key().decode())


@pytest.fixture
def key() -> str:
    return f"audit_test_{uuid.uuid4().hex[:8]}.api_key"


@pytest.mark.integration
async def test_read_is_recorded_without_the_caller_committing(
    service: SecretsService, key: str
) -> None:
    async with get_session() as db:
        await service.set_secret(db, key, "value-1")
    async with get_session() as db:
        assert await service.get_secret(db, key, audit_context="cli:get") == "value-1"
        # no commit: the session closes with the caller's transaction open

    assert (None, "cli:get", f"Accessed secret: {key}") in await _audit_rows(key)


@pytest.mark.integration
async def test_existence_check_does_not_break_the_overwrite(
    service: SecretsService, key: str
) -> None:
    """The CLI/API overwrite flow: check, then write, in one session."""
    async with get_session() as db:
        await service.set_secret(db, key, "value-1")
    async with get_session() as db:
        await service.get_secret(db, key, audit_context="api:set:check")
        await service.set_secret(db, key, "value-2", audit_context="api:set")
    async with get_session() as db:
        assert await service.get_secret(db, key) == "value-2"


@pytest.mark.integration
async def test_rotation_store_and_delete_are_recorded(
    service: SecretsService, key: str
) -> None:
    async with get_session() as db:
        await service.set_secret(db, key, "value-1", audit_context="cli:set")
    async with get_session() as db:
        await service.rotate_secret(db, key, "value-2")
    async with get_session() as db:
        await service.delete_secret(db, key, audit_context="cli:delete")

    assert await _audit_rows(key) == [
        (None, "cli:set", f"Stored secret: {key}"),
        (None, "rotation", f"Accessed secret: {key}"),
        (None, "rotation", f"Stored secret: {key}"),
        (None, "cli:delete", f"Deleted secret: {key}"),
    ]


async def test_audit_failure_is_logged_not_raised_and_skips_caller_session() -> None:
    """No database here: the audit's own session fails to execute. The
    caller's session is never used for the audit, so it cannot be poisoned."""
    caller_db = MagicMock()
    caller_db.bind = None
    service = SecretsService(Fernet.generate_key().decode())

    await service._audit_secret_access(caller_db, "k.api_key", cognitive_role="cli:get")

    caller_db.execute.assert_not_called()
