# tests/will/autonomy/test_proposal_executor_repo_lock.py
"""A writing proposal run holds the clone's sync/commit lock (ADR-132 D10 ·
D2, C3); a lock still held after the wait blocks the proposal instead of
failing it; dry runs take no lock. Real lock file, real flock."""

from __future__ import annotations

import fcntl
import functools
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from body.infrastructure import repo_sync
from body.infrastructure.repo_sync import repo_lock
from body.infrastructure.storage.file_handler import FileHandler
from shared.exceptions import GovernanceInstrumentError
from shared.path_resolver import PathResolver
from will.autonomy import proposal_executor
from will.autonomy.proposal_executor import ProposalExecutor


def _executor(root: Path) -> tuple[ProposalExecutor, FileHandler]:
    handler = FileHandler(str(root))
    handler._guard_paths = lambda *a, **k: None  # type: ignore[method-assign]
    ctx = MagicMock()
    ctx.git_service.repo_path = root
    ctx.file_handler = handler
    return ProposalExecutor(ctx), handler


def _lock_file(root: Path) -> Path:
    return PathResolver.from_repo(root).run_dir / "repo-sync.lock"


def _lock_is_held(root: Path) -> bool:
    with _lock_file(root).open("r") as other:
        try:
            fcntl.flock(other.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(other.fileno(), fcntl.LOCK_UN)
        return False


# ID: 8b2971ae-0291-4201-8a26-e5b57915f832
async def test_writing_run_holds_the_lock(tmp_path: Path) -> None:
    executor, _ = _executor(tmp_path)
    seen: dict[str, Any] = {}

    async def body(*_a: object) -> dict[str, Any]:
        seen["held"] = _lock_is_held(tmp_path)
        return {"ok": True, "lifecycle_status": "completed"}

    executor._execute = body  # type: ignore[method-assign]
    result = await executor.execute("p", MagicMock(), write=True)
    assert result["lifecycle_status"] == "completed"
    assert seen["held"] is True
    assert _lock_is_held(tmp_path) is False


# ID: 2f192f55-9fcc-4df7-afe0-8a4d49f388cc
async def test_lock_held_elsewhere_blocks_instead_of_failing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executor, handler = _executor(tmp_path)
    monkeypatch.setattr(
        proposal_executor,
        "async_repo_lock",
        functools.partial(repo_sync.async_repo_lock, timeout_sec=0.2, poll_sec=0.05),
    )
    called = MagicMock()

    async def body(*_a: object) -> dict[str, Any]:
        called()
        return {}

    executor._execute = body  # type: ignore[method-assign]
    with repo_lock(tmp_path, handler):
        with pytest.raises(GovernanceInstrumentError, match="repo_lock"):
            await executor.execute("p", MagicMock(), write=True)
    called.assert_not_called()


# ID: 4c9cb193-2336-4a16-830a-588000f35948
async def test_dry_run_takes_no_lock(tmp_path: Path) -> None:
    executor, handler = _executor(tmp_path)

    async def body(*_a: object) -> dict[str, Any]:
        return {"lifecycle_status": "dry_run"}

    executor._execute = body  # type: ignore[method-assign]
    with repo_lock(tmp_path, handler):
        result = await executor.execute("p", MagicMock(), write=False)
    assert result["lifecycle_status"] == "dry_run"
