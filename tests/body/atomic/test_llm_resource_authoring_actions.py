# tests/body/atomic/test_llm_resource_authoring_actions.py
"""#821 Unit 3: author.llm_resource atomic action.

DB-integration tests against the live core.llm_resources table, scoped to
a synthetic, uniquely-named test resource deleted before and after each
test (same idiom as test_llm_resource_repository.py).

CAUTION: this file performs real INSERTs/UPDATEs against
core.llm_resources. Per CLAUDE.md, running a test file known to hit
shared live state is governor-initiated -- do not run this file without
asking first, even though writing it is a normal part of the change.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import MagicMock

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from body.atomic.llm_resource_authoring_actions import action_author_llm_resource
from shared.context import CoreContext
from shared.governance_token import authorize_execution
from shared.infrastructure.database.models import LlmResource
from shared.infrastructure.intent.capability_taxonomy import load_capability_taxonomy


pytestmark = [pytest.mark.integration]

_ACTION_ID = "author.llm_resource"
_TEST_NAME = "test_llm_resource_821_unit3_action"
_TEST_ENV_PREFIX = "TEST_821_UNIT3_ACTION"


@pytest.fixture(autouse=True)
# ID: 8d2f6b0a-4c9e-4d1f-b6a0-4e8d2f6b0a4c
async def _cleanup_test_resource(
    db_session: AsyncSession,
) -> AsyncGenerator[None, None]:
    async def _delete() -> None:
        await db_session.execute(
            delete(LlmResource).where(LlmResource.name == _TEST_NAME)
        )
        await db_session.commit()

    await _delete()
    try:
        yield
    finally:
        await _delete()


def _core_context() -> CoreContext:
    return CoreContext(
        registry=MagicMock(),
        git_service=MagicMock(),
        knowledge_service=MagicMock(),
        file_handler=MagicMock(),
        file_service=MagicMock(),
    )


async def _run(*, write: bool, definition: dict | None):
    with authorize_execution(_ACTION_ID):
        return await action_author_llm_resource(
            core_context=_core_context(), write=write, definition=definition
        )


def _valid_definition(**overrides) -> dict:
    canonical = sorted(load_capability_taxonomy())
    base = {
        "name": _TEST_NAME,
        "env_prefix": _TEST_ENV_PREFIX,
        "provided_capabilities": canonical[:1],
        "model_name": "test-model",
        "locality": "local",
    }
    base.update(overrides)
    return base


# ID: 9e3c7a1f-5b8d-4e2c-c0d4-6f0b4d8e2c6a
async def test_write_false_validates_without_persisting(
    db_session: AsyncSession,
) -> None:
    result = await _run(write=False, definition=_valid_definition())
    assert result.ok is True
    assert result.data["valid"] is True
    assert result.data["dry_run"] is True

    check = await db_session.execute(
        select(LlmResource).where(LlmResource.name == _TEST_NAME)
    )
    assert check.scalar_one_or_none() is None


# ID: 0f4b8d2e-6c1a-4f3d-d5e9-7a1c5e9f3b7d
async def test_write_true_persists_valid_definition(db_session: AsyncSession) -> None:
    result = await _run(write=True, definition=_valid_definition())
    assert result.ok is True
    assert result.data["resource"]["name"] == _TEST_NAME

    check = await db_session.execute(
        select(LlmResource).where(LlmResource.name == _TEST_NAME)
    )
    assert check.scalar_one_or_none() is not None


# ID: 1a5c9e3f-7d0b-4a4e-e6f0-8b2d6a0c4e8f
async def test_missing_definition_fails_closed() -> None:
    result = await _run(write=False, definition=None)
    assert result.ok is False
    assert "definition is required" in result.data["error"]


# ID: 2b6d0f4a-8e1c-4b5f-f7a1-9c3e7b1d5a9c
async def test_non_canonical_capability_reported_and_not_persisted(
    db_session: AsyncSession,
) -> None:
    result = await _run(
        write=True,
        definition=_valid_definition(provided_capabilities=["not_a_real_capability"]),
    )
    assert result.ok is False
    assert result.data["valid"] is False
    assert any("non-canonical" in v for v in result.data["violations"])

    check = await db_session.execute(
        select(LlmResource).where(LlmResource.name == _TEST_NAME)
    )
    assert check.scalar_one_or_none() is None
