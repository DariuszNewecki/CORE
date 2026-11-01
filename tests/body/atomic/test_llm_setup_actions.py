# tests/body/atomic/test_llm_setup_actions.py
"""#1374: setup.llm gives a fresh install a working embedding and chat model.

Unit tests prove the two rows cover every cognitive role the taxonomy
declares, and that bad input fails before the database is touched. The
integration tests write to core.system_config and core.llm_resources and
restore both afterwards.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import MagicMock

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from body.atomic.llm_setup_actions import (
    CHAT_RESOURCE,
    EMBEDDING_RESOURCE,
    action_setup_llm,
    build_setup_definitions,
)
from shared.context import CoreContext
from shared.governance_token import authorize_execution
from shared.infrastructure.database.models import LlmResource, SystemConfig
from shared.infrastructure.intent.capability_taxonomy import load_capability_taxonomy
from shared.infrastructure.intent.cognitive_roles import (
    load_cognitive_role_capabilities,
)


_ACTION_ID = "setup.llm"


def _core_context() -> CoreContext:
    return CoreContext(
        registry=MagicMock(),
        git_service=MagicMock(),
        knowledge_service=MagicMock(),
        file_handler=MagicMock(),
        file_service=MagicMock(),
    )


async def _run(**kwargs):
    args = {
        "api_url": "http://localhost:11434",
        "embedding_model": "nomic-embed-text",
        "chat_model": "qwen2.5-coder:7b",
        "locality": "local",
    }
    args.update(kwargs)
    with authorize_execution(_ACTION_ID):
        return await action_setup_llm(core_context=_core_context(), **args)


def test_every_declared_role_is_served_by_one_of_the_two_rows() -> None:
    """The newcomer registers two models; no role may be left without one."""
    definitions = build_setup_definitions(
        api_url="http://x",
        embedding_model="e",
        chat_model="c",
        locality="local",
        canonical=frozenset(load_capability_taxonomy()),
    )
    provided = [set(d["provided_capabilities"]) for d in definitions]
    roles = load_cognitive_role_capabilities()
    assert roles  # the taxonomy is not empty
    unserved = {
        role: sorted(needed)
        for role, needed in roles.items()
        if not any(set(needed) <= caps for caps in provided)
    }
    assert unserved == {}


def test_embedding_row_only_embeds() -> None:
    embedding, chat = build_setup_definitions(
        api_url="http://x",
        embedding_model="e",
        chat_model="c",
        locality="remote",
        canonical=frozenset(load_capability_taxonomy()),
    )
    assert embedding["provided_capabilities"] == ["embedding"]
    assert "embedding" not in chat["provided_capabilities"]
    assert {embedding["locality"], chat["locality"]} == {"remote"}


def test_embeddings_can_stay_local_beside_a_hosted_chat_model() -> None:
    embedding, chat = build_setup_definitions(
        api_url="https://api.anthropic.com/v1",
        embedding_model="nomic-embed-text",
        chat_model="claude",
        locality="remote",
        canonical=frozenset(load_capability_taxonomy()),
        embedding_api_url="http://localhost:11434",
        embedding_locality="local",
    )
    assert (embedding["api_url"], embedding["locality"]) == (
        "http://localhost:11434",
        "local",
    )
    assert (chat["api_url"], chat["locality"]) == (
        "https://api.anthropic.com/v1",
        "remote",
    )


@pytest.mark.parametrize(
    "kwargs",
    [{"api_url": ""}, {"embedding_model": ""}, {"chat_model": ""}],
)
async def test_missing_input_fails_before_the_database(kwargs: dict) -> None:
    result = await _run(write=True, **kwargs)
    assert result.ok is False
    assert "required" in result.data["error"]


async def test_unknown_locality_fails_before_the_database() -> None:
    result = await _run(write=True, locality="cloud")
    assert result.ok is False
    assert "locality" in result.data["error"]


# ── integration: real core.system_config / core.llm_resources ───────────────


@pytest.fixture
async def _restore_state(
    db_session: AsyncSession,
) -> AsyncGenerator[None, None]:
    """Remove the setup rows and any system_config row; restore afterwards."""
    saved = [
        {
            "operating_mode": c.operating_mode,
            "llm_enabled": c.llm_enabled,
            "request_timeout_seconds": c.request_timeout_seconds,
            "embed_model_revision": c.embed_model_revision,
            "log_retention_months": c.log_retention_months,
        }
        for c in (await db_session.execute(select(SystemConfig))).scalars()
    ]

    async def _clear() -> None:
        await db_session.execute(
            delete(LlmResource).where(
                LlmResource.name.in_([EMBEDDING_RESOURCE, CHAT_RESOURCE])
            )
        )
        await db_session.execute(delete(SystemConfig))
        await db_session.commit()

    await _clear()
    try:
        yield
    finally:
        await _clear()
        for row in saved:
            db_session.add(SystemConfig(**row))
        await db_session.commit()


async def _state(db_session: AsyncSession) -> tuple[list, list]:
    db_session.expire_all()
    configs = [
        (c.operating_mode, c.llm_enabled)
        for c in (await db_session.execute(select(SystemConfig))).scalars()
    ]
    resources = sorted(
        (r.name, r.model_name, r.locality, r.is_available)
        for r in (
            await db_session.execute(
                select(LlmResource).where(
                    LlmResource.name.in_([EMBEDDING_RESOURCE, CHAT_RESOURCE])
                )
            )
        ).scalars()
    )
    return configs, resources


@pytest.mark.integration
@pytest.mark.usefixtures("_restore_state")
async def test_dry_run_writes_nothing(db_session: AsyncSession) -> None:
    result = await _run(write=False)
    assert result.ok is True, result.data
    assert result.data["dry_run"] is True
    assert result.data["system_config"] == "created (local_only, llm enabled)"
    assert await _state(db_session) == ([], [])


@pytest.mark.integration
@pytest.mark.usefixtures("_restore_state")
async def test_fresh_database_gets_settings_and_both_models(
    db_session: AsyncSession,
) -> None:
    result = await _run(write=True)
    assert result.ok is True, result.data
    assert await _state(db_session) == (
        [("local_only", True)],
        [
            (CHAT_RESOURCE, "qwen2.5-coder:7b", "local", True),
            (EMBEDDING_RESOURCE, "nomic-embed-text", "local", True),
        ],
    )


@pytest.mark.integration
@pytest.mark.usefixtures("_restore_state")
async def test_rerun_updates_models_and_remote_leaves_local_only(
    db_session: AsyncSession,
) -> None:
    assert (await _run(write=True)).ok
    result = await _run(
        write=True,
        api_url="https://models.example/v1",
        chat_model="chat-2",
        locality="remote",
    )
    assert result.ok is True, result.data
    assert result.data["system_config"] == "operating_mode local_only -> hybrid"
    assert result.data["remote_env_prefixes"] == ["setup_embedding", "setup_chat"]
    assert await _state(db_session) == (
        [("hybrid", True)],
        [
            (CHAT_RESOURCE, "chat-2", "remote", True),
            (EMBEDDING_RESOURCE, "nomic-embed-text", "remote", True),
        ],
    )
