"""Tests for DeadCodeCheck (#585): subprocess invocation delegates to the
shared sanctuary (shared.utils.subprocess_utils.run_vulture).

Pre-#585, DeadCodeCheck.verify called asyncio.create_subprocess_exec inline,
placing subprocess semantics inside the Mind layer (violation of
architecture.layers.no_mind_execution). The refactored shape delegates the
subprocess call to the shared sanctuary; this file verifies the delegation
+ structured-result handling, not subprocess behaviour itself.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from mind.logic.engines.workflow_gate.checks.dead_code import DeadCodeCheck
from shared.path_resolver import PathResolver
from shared.utils.subprocess_utils import SubprocessResult


def _make_check(repo_root: Path) -> DeadCodeCheck:
    """Construct a DeadCodeCheck pointed at a synthetic repo root."""
    resolver = PathResolver(repo_root=repo_root)
    return DeadCodeCheck(path_resolver=resolver)


# ID: f78bc79a-d3b0-4ce3-9d4c-02ffdc5130cd
async def test_verify_delegates_to_run_vulture(tmp_path: Path) -> None:
    """DeadCodeCheck.verify must route the vulture invocation through
    shared.utils.subprocess_utils.run_vulture — not call subprocess directly.
    """
    check = _make_check(tmp_path)
    fake_result = SubprocessResult(stdout="", stderr="", returncode=0)

    with patch(
        "mind.logic.engines.workflow_gate.checks.dead_code.run_vulture",
        new=AsyncMock(return_value=fake_result),
    ) as mock_vulture:
        await check.verify(file_path=None, params={"confidence": 70})

    mock_vulture.assert_awaited_once()
    call_kwargs = mock_vulture.await_args.kwargs
    assert call_kwargs["target"] == "src/"
    assert call_kwargs["confidence"] == 70
    assert call_kwargs["repo_root"] == tmp_path


# ID: 6f998275-64c5-42a0-8ffa-1f5751e08970
async def test_verify_returns_empty_when_vulture_finds_nothing(
    tmp_path: Path,
) -> None:
    """A clean vulture run (empty stdout) produces no violations."""
    check = _make_check(tmp_path)
    fake_result = SubprocessResult(stdout="", stderr="", returncode=0)

    with patch(
        "mind.logic.engines.workflow_gate.checks.dead_code.run_vulture",
        new=AsyncMock(return_value=fake_result),
    ):
        violations = await check.verify(file_path=None, params={})

    assert violations == []


# ID: b3c9ccf0-5c86-4c01-bd30-2308483e95c2
async def test_verify_emits_one_violation_per_vulture_line(tmp_path: Path) -> None:
    """Each line of vulture's stdout becomes one violation, prefixed
    'Dead code detected: '. Matches pre-#585 output shape so dashboards /
    downstream consumers see no regression.
    """
    check = _make_check(tmp_path)
    fake_stdout = (
        "src/foo.py:12: unused function 'bar' (60% confidence)\n"
        "src/baz.py:3: unused import 'qux' (90% confidence)\n"
    )
    fake_result = SubprocessResult(stdout=fake_stdout, stderr="", returncode=0)

    with patch(
        "mind.logic.engines.workflow_gate.checks.dead_code.run_vulture",
        new=AsyncMock(return_value=fake_result),
    ):
        violations = await check.verify(file_path=None, params={})

    assert len(violations) == 2
    assert all(v.startswith("Dead code detected: ") for v in violations)
    assert "src/foo.py:12" in violations[0]
    assert "src/baz.py:3" in violations[1]


# ID: 2ec7648b-0d73-476d-a2ef-a182aa3dc974
async def test_verify_recovers_from_sanctuary_failure(tmp_path: Path) -> None:
    """If run_vulture raises (e.g. binary missing, transient OS error), the
    check returns a single 'Dead code analysis failed: ...' violation rather
    than propagating the exception. Preserves pre-#585 failure semantics so
    the engine sees a structured violation, not an unhandled exception.
    """
    check = _make_check(tmp_path)

    with patch(
        "mind.logic.engines.workflow_gate.checks.dead_code.run_vulture",
        new=AsyncMock(side_effect=FileNotFoundError("vulture not found")),
    ):
        violations = await check.verify(file_path=None, params={})

    assert len(violations) == 1
    assert violations[0].startswith("Dead code analysis failed: ")
    assert "vulture not found" in violations[0]


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
