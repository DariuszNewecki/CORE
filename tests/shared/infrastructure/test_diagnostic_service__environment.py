# tests/shared/infrastructure/test_diagnostic_service__environment.py
"""#915: a missing LLM key or master key is optional, not 'degraded infrastructure'."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from shared.infrastructure import diagnostic_service as ds


def _settings(**overrides) -> SimpleNamespace:
    base = {
        "DATABASE_URL": "postgresql+asyncpg://x",
        "QDRANT_URL": "http://localhost:6333",
        "LLM_API_KEY": None,
        "CORE_MASTER_KEY": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fail_session():
        raise RuntimeError("no db in unit test")

    monkeypatch.setattr(ds, "get_session", _fail_session)
    monkeypatch.setattr(
        ds, "QdrantService", MagicMock(side_effect=RuntimeError("no qdrant"))
    )


# ID: 506335c2-7c5d-41ce-8d59-89308c1efde4
async def test_no_llm_key_and_no_master_key_is_ok(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ds, "settings", _settings())

    env = (await ds.DiagnosticService(Path(".")).check_connectivity())["environment"]

    assert env["ok"] is True
    assert "LLM_API_KEY" in env["detail"] and "optional" in env["detail"]


# ID: f840e515-c340-4ca6-bdac-cf8184f12185
async def test_missing_database_url_is_not_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ds, "settings", _settings(DATABASE_URL=None))

    env = (await ds.DiagnosticService(Path(".")).check_connectivity())["environment"]

    assert env["ok"] is False
    assert "DATABASE_URL" in env["detail"]


# ID: aee1b440-b169-40c9-834d-852ab7369cd6
async def test_all_set_has_no_optional_note(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ds, "settings", _settings(LLM_API_KEY="k", CORE_MASTER_KEY="m"))

    env = (await ds.DiagnosticService(Path(".")).check_connectivity())["environment"]

    assert env == {"ok": True, "detail": "Required coordinates present"}
