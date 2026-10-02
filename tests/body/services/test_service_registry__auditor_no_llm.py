# tests/body/services/test_service_registry__auditor_no_llm.py
"""#915: with no LLM configured the auditor says so in one INFO line.

Before: ERROR "Role 'LocalCoder' not found in Mind" plus a WARNING on a
healthy no-LLM install. Other LLM failures keep their WARNING.
"""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from body.services import service_registry as sr
from body.services.service_registry import ServiceRegistry
from shared.exceptions import NoLLMConfiguredError


async def _auditor_with(
    monkeypatch: pytest.MonkeyPatch, exc: Exception
) -> ServiceRegistry:
    # _instances is a ClassVar shared by every ServiceRegistry: give this test
    # its own dict (restored afterwards) so the mocked AuditorContext cannot
    # leak into the process-wide registry or other tests.
    monkeypatch.setattr(ServiceRegistry, "_instances", {})
    registry = ServiceRegistry()
    cog = MagicMock()
    cog.aget_client_for_role = AsyncMock(side_effect=exc)
    monkeypatch.setattr(registry, "get_cognitive_service", AsyncMock(return_value=cog))
    monkeypatch.setattr(sr.bootstrap_registry, "get_repo_path", lambda: Path("."))
    monkeypatch.setattr(
        "mind.governance.audit_context.AuditorContext", MagicMock(name="AuditorContext")
    )
    await registry.get_auditor_context()
    return registry


# ID: a6ede1bf-3a0a-4fe8-ac21-cad86a714e1c
async def test_no_llm_configured_is_one_info_line(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG, logger="body.services.service_registry"):
        await _auditor_with(monkeypatch, NoLLMConfiguredError("LocalCoder"))

    records = [r for r in caplog.records if r.name == "body.services.service_registry"]
    assert any(
        r.levelno == logging.INFO and "no LLM configured" in r.message for r in records
    )
    assert not [r for r in records if r.levelno >= logging.WARNING]


# ID: d798bb18-f0e5-4972-bf7b-4e6358d87369
async def test_other_llm_failure_keeps_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG, logger="body.services.service_registry"):
        await _auditor_with(monkeypatch, RuntimeError("provider unreachable"))

    assert any(
        r.levelno == logging.WARNING and "falling back to stub" in r.message
        for r in caplog.records
    )
