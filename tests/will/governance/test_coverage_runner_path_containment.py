# tests/will/governance/test_coverage_runner_path_containment.py
"""#817: coverage_runner's existence-check call sites must reject a
target_file that resolves outside repo_root *before* touching the
filesystem — a bare (repo_root / target_file).resolve() does not, by
itself, reject a traversal result, only resolve_contained_source_path does.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from will.governance.coverage_runner import (
    run_and_persist_coverage_generation,
    run_tests_interactive,
)


def _context(repo_root: Path) -> MagicMock:
    context = MagicMock()
    context.git_service.repo_path = repo_root
    context.cognitive_service = MagicMock()
    return context


async def test_generation_rejects_traversal_target_file_before_touching_disk(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path)
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    run_id = uuid4()

    await run_and_persist_coverage_generation(
        context,
        session,
        run_id=run_id,
        target_file="src/../../../../../../etc/passwd",
        write=True,
    )

    last_params = session.execute.await_args_list[-1].args[1]
    assert last_params["status"] == "failed"
    assert "resolves outside repo_root" in last_params["err"]


async def test_interactive_rejects_traversal_target_file_before_touching_disk(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path)

    result = await run_tests_interactive(
        context, target_file="src/../../../../../../etc/passwd"
    )

    assert result["ok"] is False
    assert "resolves outside repo_root" in result["error"]


async def test_generation_accepts_contained_missing_file_with_normal_error(
    tmp_path: Path,
) -> None:
    """A contained-but-nonexistent path is a different, expected failure
    mode ("does not exist") — the containment check must not swallow it."""
    context = _context(tmp_path)
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    run_id = uuid4()

    await run_and_persist_coverage_generation(
        context,
        session,
        run_id=run_id,
        target_file="src/does_not_exist.py",
        write=True,
    )

    last_params = session.execute.await_args_list[-1].args[1]
    assert last_params["status"] == "failed"
    assert "does not exist" in last_params["err"]
