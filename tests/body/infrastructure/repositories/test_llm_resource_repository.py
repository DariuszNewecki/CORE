# tests/body/infrastructure/repositories/test_llm_resource_repository.py
"""#821 Unit 3: LlmResourceRepository.

DB-integration tests against the live core.llm_resources table (excluded
from the autouse TRUNCATE-between-tests fixture per tests/conftest.py,
since it is shared config/registry state). Every test uses a synthetic,
uniquely-named test resource and deletes it before and after, so the
shared table is left exactly as found regardless of test outcome.

CAUTION: this file performs real INSERTs/UPDATEs/DELETEs against
core.llm_resources, scoped to a synthetic row. Per CLAUDE.md, running a
test file known to hit shared live state is governor-initiated -- do not
run this file without asking first, even though writing it is a normal
part of the change.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from body.infrastructure.repositories.llm_resource_repository import (
    LlmResourceRepository,
    LlmResourceValidationError,
    validate_llm_resource_definition,
)
from shared.infrastructure.database.models import LlmResource
from shared.infrastructure.intent.capability_taxonomy import load_capability_taxonomy


pytestmark = [pytest.mark.integration]

_TEST_NAME = "test_llm_resource_821_unit3"
_TEST_ENV_PREFIX = "TEST_821_UNIT3"


@pytest.fixture(autouse=True)
# ID: 1c5a9e3f-7d0b-4c8e-a2f6-0b4d8e2c6a0f
async def _cleanup_test_resource(
    db_session: AsyncSession,
) -> AsyncGenerator[None, None]:
    """Delete the synthetic test row before and after every test."""

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


def _canonical() -> frozenset[str]:
    return load_capability_taxonomy()


def _valid_definition(**overrides) -> dict:
    canonical = sorted(_canonical())
    base = {
        "name": _TEST_NAME,
        "env_prefix": _TEST_ENV_PREFIX,
        "provided_capabilities": canonical[:1],
        "model_name": "test-model",
        "locality": "local",
    }
    base.update(overrides)
    return base


# ID: 2d6b0f4a-8e1c-4d9f-b3a7-1c5e9d3f7a1c
async def test_upsert_creates_new_resource(db_session: AsyncSession) -> None:
    async with LlmResourceRepository.open() as repo:
        resource = await repo.upsert(_valid_definition())

    assert resource.name == _TEST_NAME
    assert resource.env_prefix == _TEST_ENV_PREFIX
    assert resource.is_available is True

    async with LlmResourceRepository.open() as repo:
        fetched = await repo.get(_TEST_NAME)
    assert fetched is not None
    assert fetched.name == _TEST_NAME


# ID: 3e7c1a5c-9f2d-4e0a-c4b8-2d6f0a4c8e2d
async def test_upsert_updates_existing_resource_in_place(
    db_session: AsyncSession,
) -> None:
    canonical = sorted(_canonical())
    async with LlmResourceRepository.open() as repo:
        await repo.upsert(_valid_definition(provided_capabilities=canonical[:1]))

    async with LlmResourceRepository.open() as repo:
        updated = await repo.upsert(
            _valid_definition(provided_capabilities=canonical, api_url="http://x")
        )

    assert updated.name == _TEST_NAME
    assert set(updated.provided_capabilities) == set(canonical)
    assert updated.api_url == "http://x"

    async with LlmResourceRepository.open() as repo:
        count_check = await repo.get(_TEST_NAME)
    assert count_check is not None  # still exactly one row, not duplicated


# ID: 4f8d2b6c-0a3e-4f1b-d5c9-3e7a1c5f9d3e
async def test_non_canonical_capability_raises_and_does_not_persist(
    db_session: AsyncSession,
) -> None:
    async with LlmResourceRepository.open() as repo:
        with pytest.raises(LlmResourceValidationError, match="non-canonical"):
            await repo.upsert(
                _valid_definition(provided_capabilities=["not_a_real_capability"])
            )

    async with LlmResourceRepository.open() as repo:
        assert await repo.get(_TEST_NAME) is None


# ID: 5a9e3c7d-1b4f-4a2c-e6d0-4f8b2d6a0c4f
async def test_missing_model_name_when_available_raises() -> None:
    canonical = sorted(_canonical())
    definition = _valid_definition(provided_capabilities=canonical[:1])
    del definition["model_name"]
    violations = validate_llm_resource_definition(definition, frozenset(canonical))
    assert any("model_name" in v for v in violations)


# ID: 6b0f4d8e-2c5a-4b3d-f7e1-5a9c3e7d1b4f
def test_validate_missing_required_fields() -> None:
    violations = validate_llm_resource_definition({}, frozenset({"reasoning"}))
    assert any("name" in v for v in violations)
    assert any("env_prefix" in v for v in violations)


# ID: 7c1a5e9f-3d6b-4c4e-a8f2-6b0d4f8e2c5a
def test_validate_invalid_locality() -> None:
    definition = {
        "name": "x",
        "env_prefix": "X",
        "provided_capabilities": [],
        "locality": "orbital",
    }
    violations = validate_llm_resource_definition(definition, frozenset())
    assert any("locality" in v for v in violations)
