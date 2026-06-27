# tests/shared/workers/test_base__load_declaration.py
"""Unit tests for Worker._load_declaration gateway routing.

Verifies that _load_declaration routes through IntentRepository (the canonical
.intent/ gateway) rather than constructing Path(".intent") directly.
Covers: success path, missing declaration, load failure, and explicit repo_root.
"""

from __future__ import annotations

from pathlib import Path
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


# ID: 4f8a2e1c-9b3d-4a5f-8c7e-1d2f3e4a5b6c
def test_load_declaration_uses_explicit_repo_root_not_global_singleton() -> None:
    """When repo_root is provided, _load_declaration uses IntentRepository(root=...) and
    does NOT call get_intent_repository() — bypasses the CWD-dependent singleton (#690)."""
    mock_repo = MagicMock()
    mock_repo.load_worker.return_value = _VALID_DECLARATION
    explicit_root = Path("/fake/repo/root")

    with (
        patch("shared.workers.base.IntentRepository", return_value=mock_repo) as mock_cls,
        patch("shared.workers.base.get_intent_repository") as mock_global,
        patch("shared.workers.base.validate_worker_declaration"),
    ):
        worker = _StubWorker.__new__(_StubWorker)
        worker.declaration_name = "stub_worker"
        worker._repo_root = explicit_root
        result = worker._load_declaration()

    mock_cls.assert_called_once_with(
        root=explicit_root / ".intent", strict=True
    )
    mock_global.assert_not_called()
    mock_repo.load_worker.assert_called_once_with("workers/stub_worker")
    assert result == _VALID_DECLARATION


# ID: 5c9b3f2d-0e4a-4b6c-8d1e-2a3f4c5d6e7f
def test_load_declaration_falls_back_to_singleton_when_no_repo_root() -> None:
    """Without repo_root, _load_declaration falls back to get_intent_repository()
    (existing behavior preserved for tests and bare instantiation)."""
    mock_repo = MagicMock()
    mock_repo.load_worker.return_value = _VALID_DECLARATION

    with (
        patch("shared.workers.base.get_intent_repository", return_value=mock_repo),
        patch("shared.workers.base.IntentRepository") as mock_cls,
        patch("shared.workers.base.validate_worker_declaration"),
    ):
        worker = _StubWorker.__new__(_StubWorker)
        worker.declaration_name = "stub_worker"
        # _repo_root not set (simulates __new__ without __init__)
        result = worker._load_declaration()

    mock_cls.assert_not_called()
    mock_repo.load_worker.assert_called_once_with("workers/stub_worker")
    assert result == _VALID_DECLARATION
