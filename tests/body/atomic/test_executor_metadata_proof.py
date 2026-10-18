# tests/body/atomic/test_executor_metadata_proof.py

"""Every metadata-only action is refused when it changes logic.

Governor decision 2026-10-18: every action declared WRITE_METADATA must run
the before/after metadata check and be refused when it fails. ActionExecutor
runs such an action in metadata_only_scope and FileHandler checks each .py
write (body.governance.metadata_proof). One case per registered
action below: its real id and declared impact run through the real executor
with a body that writes a logic change through FileHandler. A new
metadata-only action fails test_every_metadata_only_action_is_covered until
it gets its case here.
"""

from __future__ import annotations

import asyncio
import dataclasses
import importlib
import pkgutil
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

import body
from body.atomic.action_audit import ActionAuditRecorder
from body.atomic.executor import ActionExecutor
from body.atomic.registry import ActionRegistry, action_registry
from body.infrastructure.storage.file_handler import FileHandler
from shared.action_types import ActionImpact, ActionResult


METADATA_ONLY_ACTIONS = [
    "file.tag_metadata",
    "fix.capability_tagging",
    "fix.duplicate_ids",
    "log.archive_partitions",
    "log.maintain_partitions",
    "sync.db",
    "sync.vectors_code",
    "sync.vectors_constitution",
]

REL = "src/pkg/mod.py"
ORIGINAL = "def handler():\n    return 1\n"
LOGIC_CHANGE = "def handler():\n    return 2\n"


def _load_all_actions() -> None:
    for module in pkgutil.walk_packages(body.__path__, "body."):
        try:
            importlib.import_module(module.name)
        except Exception:
            continue


def _metadata_only_ids() -> set[str]:
    _load_all_actions()
    return {
        d.action_id
        for d in action_registry.list_all()
        if getattr(getattr(d.executor, "_atomic_action_metadata", None), "impact", None)
        == ActionImpact.WRITE_METADATA
    }


def _executor(registry: ActionRegistry, repo: Path) -> ActionExecutor:
    executor = ActionExecutor.__new__(ActionExecutor)
    executor.core_context = MagicMock()
    executor.core_context.git_service.repo_path = repo
    executor.registry = registry
    sandbox = MagicMock()
    sandbox.build_execution_context.return_value = (executor.core_context, None)
    executor._sandbox = sandbox
    return executor


def _registry_with_body(action_id: str, body_fn: Any) -> ActionRegistry:
    """The real definition of *action_id*, its body swapped for *body_fn*."""
    _load_all_actions()
    real = action_registry.get(action_id)
    assert real is not None, f"{action_id} is not registered"
    body_fn._atomic_action_metadata = real.executor._atomic_action_metadata
    registry = ActionRegistry()
    registry.register(
        dataclasses.replace(
            real, executor=body_fn, policies=[], artifact_type=(), impact_level="safe"
        )
    )
    return registry


def _writer(repo: Path, action_id: str, content: str) -> Any:
    async def _write(**_kwargs: Any) -> ActionResult:
        FileHandler(str(repo)).write(REL, content)
        return ActionResult(action_id=action_id, ok=True, data={}, duration_sec=0.0)

    return _write


def _repo(tmp_path: Path) -> Path:
    target = tmp_path / REL
    target.parent.mkdir(parents=True)
    target.write_text(ORIGINAL, encoding="utf-8")
    return target


@pytest.fixture(autouse=True)
def _no_audit_persistence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ActionAuditRecorder, "record", AsyncMock())


@pytest.fixture(autouse=True)
def _no_path_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    """IntentGuard's fs_profiles already keep some of these actions out of src/;
    switch it off so each case proves the metadata check itself."""
    monkeypatch.setattr(FileHandler, "_guard_paths", lambda *args, **kwargs: None)


def test_every_metadata_only_action_is_covered() -> None:
    assert _metadata_only_ids() == set(METADATA_ONLY_ACTIONS)


@pytest.mark.parametrize("action_id", METADATA_ONLY_ACTIONS)
async def test_logic_change_is_refused(tmp_path: Path, action_id: str) -> None:
    target = _repo(tmp_path)
    registry = _registry_with_body(
        action_id, _writer(tmp_path, action_id, LOGIC_CHANGE)
    )

    result = await _executor(registry, tmp_path).execute(action_id, write=True)

    assert result.ok is False
    assert result.data["rule_id"] == "metadata.semantic_preservation"
    assert result.data["refusal"]["path"] == REL
    assert target.read_text(encoding="utf-8") == ORIGINAL


async def test_comment_only_change_passes(tmp_path: Path) -> None:
    target = _repo(tmp_path)
    edited = "def handler():\n    # why it returns 1\n    return 1\n"
    registry = _registry_with_body("sync.db", _writer(tmp_path, "sync.db", edited))

    result = await _executor(registry, tmp_path).execute("sync.db", write=True)

    assert result.ok is True
    assert "return 1" in target.read_text(encoding="utf-8")
    assert "# why it returns 1" in target.read_text(encoding="utf-8")


async def test_overlong_comment_is_refused(tmp_path: Path) -> None:
    target = _repo(tmp_path)
    edited = "def handler():\n    # " + "x" * 150 + "\n    return 1\n"
    registry = _registry_with_body("sync.db", _writer(tmp_path, "sync.db", edited))

    result = await _executor(registry, tmp_path).execute("sync.db", write=True)

    assert result.ok is False
    assert result.data["rule_id"] == "metadata.operations.comment_length_limit"
    assert target.read_text(encoding="utf-8") == ORIGINAL


async def test_concurrent_write_outside_the_action_is_not_refused(
    tmp_path: Path,
) -> None:
    """Another task's write during a metadata-only action is not that action's."""
    target = _repo(tmp_path)
    other = tmp_path / "src" / "pkg" / "other.py"
    started, release = asyncio.Event(), asyncio.Event()

    async def _waits(**_kwargs: Any) -> ActionResult:
        started.set()
        await release.wait()
        return ActionResult(action_id="sync.db", ok=True, data={}, duration_sec=0.0)

    async def _other_task() -> None:
        await started.wait()
        FileHandler(str(tmp_path)).write("src/pkg/other.py", "y = 2\n")
        release.set()

    registry = _registry_with_body("sync.db", _waits)
    task = asyncio.create_task(_other_task())
    result = await _executor(registry, tmp_path).execute("sync.db", write=True)
    await task

    assert result.ok is True
    assert other.read_text(encoding="utf-8") == "y = 2\n"
    assert target.read_text(encoding="utf-8") == ORIGINAL
