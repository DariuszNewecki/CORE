# tests/will/governance/test_coverage_runner__sandbox.py
"""Coverage reports run the suite in the sandbox (ADR-132 D10.10, M2)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from body.sandbox.models import SandboxResult
from will.governance.coverage_runner import (
    get_coverage_html_report,
    get_coverage_report,
)


_CTX = SimpleNamespace(git_service=SimpleNamespace(repo_path=Path("/repo")))


async def test_text_report_is_the_sandbox_coverage_table() -> None:
    result = SandboxResult(
        status="passed",
        completeness="partial",
        isolation="service",
        reason="integration tests excluded",
        exit_code=0,
        coverage={"text": "Name  Cover\nsrc/a.py  50%\nTOTAL  50%"},
    )
    with patch(
        "body.sandbox.repo_tests.run_in_sandbox", new=AsyncMock(return_value=result)
    ) as run:
        out = await get_coverage_report(_CTX)  # type: ignore[arg-type]
    assert out["stdout_tail"][-1] == "TOTAL  50%"
    assert out["ok"] is False  # partial is never ok
    assert "integration tests excluded" in out["summary"]
    assert run.await_args.kwargs["coverage"] is True


async def test_html_report_is_unavailable_and_runs_nothing() -> None:
    with patch("body.sandbox.repo_tests.run_in_sandbox", new=AsyncMock()) as run:
        out = await get_coverage_html_report(_CTX)  # type: ignore[arg-type]
    assert out["ok"] is False and out["html_path"] is None
    assert "sandbox" in out["summary"]
    assert not run.called
