# tests/shared/workers/test_base__load_declaration.py
"""Unit tests for Worker._load_declaration gateway routing.

Verifies that _load_declaration routes through IntentRepository (the canonical
.intent/ gateway) rather than constructing Path(".intent") directly.
Covers: success path, missing declaration, and load failure.
"""

from __future__ import annotations

from typing import ClassVar
from unittest.mock import MagicMock, patch

import pytest

from shared.infrastructure.intent.errors import GovernanceError
from shared.workers.base import Worker, WorkerConfigurationError


# ── Minimal concrete Worker for testing ───────────────────────────────────────

class _StubWorker(Worker):
    declaration_name: ClassVar[str] = "stub_worker"

    async def run(self) -> None:
        return


_VALID_DECLARATION: dict = {
    "kind": "worker",
    "metadata": {"id": "workers.stub_worker", "title": "Stub Worker", "version": "1.0.0",
                 "authority": "policy", "status": "active"},
    "identity": {"uuid": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "class": "sensing"},
    "mandate": {
        "responsibility": "Test stub.",
        "phase": "audit",
        "permitted_tools": [],
        "scope": {},
        "approval_required": False,
        "schedule": {"max_interval": 300},
    },
    "implementation": {},
}


# ── Tests ──────────────────────────────────────────────────────────────────────

# ID: e667fa06-416c-4e39-b10c-5b4833bb7d08
def test_load_declaration_uses_intent_repository() -> None:
    """_load_declaration calls get_intent_repository().load_worker(), not Path('.intent')."""
    mock_repo = MagicMock()
    mock_repo.load_worker.return_value = _VALID_DECLARATION

    with (
        patch(
            "shared.workers.base.get_intent_repository",
            return_value=mock_repo,
        ),
        patch("shared.workers.base.validate_worker_declaration"),
    ):
        worker = _StubWorker.__new__(_StubWorker)
        worker.declaration_name = "stub_worker"
        result = worker._load_declaration()

    mock_repo.load_worker.assert_called_once_with("workers/stub_worker")
    assert result == _VALID_DECLARATION


# ID: 8ee82edd-597e-42fd-95dd-2c69355de456
def test_load_declaration_missing_raises_worker_configuration_error() -> None:
    """GovernanceError from load_worker is re-raised as WorkerConfigurationError."""
    mock_repo = MagicMock()
    mock_repo.load_worker.side_effect = GovernanceError("not found")

    with (
        patch("shared.workers.base.get_intent_repository", return_value=mock_repo),
        pytest.raises(WorkerConfigurationError, match="no constitutional standing"),
    ):
        worker = _StubWorker.__new__(_StubWorker)
        worker.declaration_name = "stub_worker"
        worker._load_declaration()


# ID: b3812dbb-4089-4b04-9fb9-c058e3dd8fa8
def test_load_declaration_unexpected_error_raises_worker_configuration_error() -> None:
    """Unexpected exceptions from load_worker are wrapped in WorkerConfigurationError."""
    mock_repo = MagicMock()
    mock_repo.load_worker.side_effect = OSError("disk error")

    with (
        patch("shared.workers.base.get_intent_repository", return_value=mock_repo),
        pytest.raises(WorkerConfigurationError, match="Failed to load"),
    ):
        worker = _StubWorker.__new__(_StubWorker)
        worker.declaration_name = "stub_worker"
        worker._load_declaration()
