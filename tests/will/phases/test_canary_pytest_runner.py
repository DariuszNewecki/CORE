# tests/will/phases/test_canary_pytest_runner.py
"""Canary PytestRunner runs the tests in the sandbox (ADR-132 D10.10, M2).

What the sandbox result becomes for its callers (the canary phase and
TestRunnerSensor): a full pass is exit 0; failures list each failed test as
``FAILED <node id>``; a timeout is exit 124; a run that did not happen, or
ran only in part, raises TestsNotRun -- never a pass.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from body.sandbox.models import SandboxResult
from will.phases.canary import pytest_runner
from will.phases.canary.pytest_runner import PytestRunner, TestsNotRun


def _runner() -> PytestRunner:
    paths = SimpleNamespace(repo_root=Path("/repo"))
    return PytestRunner(path_resolver=paths, execution_timeout=60)  # type: ignore[arg-type]


def _sandbox(monkeypatch: pytest.MonkeyPatch, **kw: object) -> AsyncMock:
    base: dict[str, object] = {
        "status": "passed",
        "completeness": "full",
        "isolation": "service",
    }
    base.update(kw)
    fake = AsyncMock(return_value=SandboxResult(**base))  # type: ignore[arg-type]
    monkeypatch.setattr(pytest_runner, "run_in_sandbox", fake)
    return fake


async def test_targets_and_timeout_reach_the_sandbox(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _sandbox(monkeypatch, exit_code=0, counts={"passed": 2})
    result = await _runner().run_tests(["tests/t.py"])
    assert result["exit_code"] == 0 and result["passed"] == 2
    assert fake.await_args.args == (Path("/repo"), ["tests/t.py"])
    assert fake.await_args.kwargs["timeout_sec"] == 60


async def test_failures_are_listed_by_node_id(monkeypatch: pytest.MonkeyPatch) -> None:
    _sandbox(
        monkeypatch,
        status="failed",
        exit_code=1,
        counts={"passed": 1, "failed": 1},
        failed_ids=["tests/t.py::test_b"],
        stdout="1 failed, 1 passed",
    )
    result = await _runner().run_tests(["tests/t.py"])
    assert (result["passed"], result["failed"], result["exit_code"]) == (1, 1, 1)
    assert "FAILED tests/t.py::test_b" in result["output"]


async def test_timeout_is_exit_124(monkeypatch: pytest.MonkeyPatch) -> None:
    _sandbox(monkeypatch, status="timeout", completeness="none")
    result = await _runner().run_tests(["tests/t.py"])
    assert result["exit_code"] == 124


@pytest.mark.parametrize(
    ("status", "completeness"),
    [("not_run", "none"), ("error", "none"), ("passed", "partial")],
)
async def test_not_run_or_partial_raises(
    monkeypatch: pytest.MonkeyPatch, status: str, completeness: str
) -> None:
    # Before: no tests collected came back as exit 0, a pass.
    _sandbox(monkeypatch, status=status, completeness=completeness, reason="why")
    with pytest.raises(TestsNotRun, match="why"):
        await _runner().run_tests(["tests/t.py"])
