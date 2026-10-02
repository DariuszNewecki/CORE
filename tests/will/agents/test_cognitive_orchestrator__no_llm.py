# tests/will/agents/test_cognitive_orchestrator__no_llm.py
"""#915: an unconfigured Mind is a state, not an error.

No cognitive roles and no resources (fresh no-LLM install) raises the typed
NoLLMConfiguredError before the selector would log "Role ... not found in Mind"
at ERROR. A role missing from a configured Mind stays a real error.
"""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.exceptions import NoLLMConfiguredError
from will.agents.cognitive_orchestrator import CognitiveOrchestrator


def _orch(roles: list, resources: list, system_config=None) -> CognitiveOrchestrator:
    mind = MagicMock()
    mind.get_llm_resources = AsyncMock(return_value=resources)
    mind.get_cognitive_roles = AsyncMock(return_value=roles)
    mind.get_role_resource_assignments = AsyncMock(return_value=[])
    mind.get_system_config = AsyncMock(return_value=system_config)
    return CognitiveOrchestrator(Path("."), mind, AsyncMock())


# ID: e58eeb2c-fae2-4465-bbb3-1b99b7993708
async def test_unconfigured_mind_raises_typed_no_llm_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    orch = _orch(roles=[], resources=[])

    with caplog.at_level(logging.DEBUG):
        with pytest.raises(NoLLMConfiguredError) as exc_info:
            await orch.get_client_for_role("LocalCoder")

    assert isinstance(exc_info.value, RuntimeError)
    assert exc_info.value.role_name == "LocalCoder"
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


# ID: 82788cb2-e9a4-4b40-83f7-f4e021d5b5ff
async def test_missing_role_in_configured_mind_is_still_an_error() -> None:
    other_role = MagicMock()
    other_role.role = "Planner"
    orch = _orch(roles=[other_role], resources=[MagicMock()])

    with pytest.raises(RuntimeError) as exc_info:
        await orch.get_client_for_role("LocalCoder")

    assert not isinstance(exc_info.value, NoLLMConfiguredError)


# ID: a34cbad4-34c9-4de7-b502-6ffa8e34bae3
async def test_missing_system_config_is_info_when_unconfigured(
    caplog: pytest.LogCaptureFixture,
) -> None:
    orch = _orch(roles=[], resources=[], system_config=None)

    with caplog.at_level(logging.DEBUG):
        await orch.initialize()

    record = next(r for r in caplog.records if "system_config row missing" in r.message)
    assert record.levelno == logging.INFO


# ID: f10ebed3-9d47-400f-a6aa-24220bd787bf
async def test_missing_system_config_is_warning_when_configured(
    caplog: pytest.LogCaptureFixture,
) -> None:
    orch = _orch(roles=[MagicMock()], resources=[MagicMock()], system_config=None)

    with caplog.at_level(logging.DEBUG):
        await orch.initialize()

    record = next(r for r in caplog.records if "system_config row missing" in r.message)
    assert record.levelno == logging.WARNING
