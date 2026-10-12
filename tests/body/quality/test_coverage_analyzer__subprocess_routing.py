# tests/body/quality/test_coverage_analyzer__subprocess_routing.py
"""CoverageAnalyzer measures coverage in the sandbox (ADR-132 D10.10, M2).

The suite runs in the sandbox runner with coverage on; the per-file numbers
come back in the result. Nothing runs as the services account, and no
coverage.json is read from the repository.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

from body.quality import coverage_analyzer
from body.quality.coverage_analyzer import CoverageAnalyzer
from body.sandbox.models import SandboxResult


_SANDBOX = "body.sandbox.repo_tests.run_in_sandbox"


def _result(**kw: object) -> SandboxResult:
    base: dict[str, object] = {
        "status": "passed",
        "completeness": "full",
        "isolation": "service",
    }
    base.update(kw)
    return SandboxResult(**base)  # type: ignore[arg-type]


async def test_coverage_comes_from_the_sandbox() -> None:
    files = {"src/a.py": 50.12}
    with patch(
        _SANDBOX, new=AsyncMock(return_value=_result(coverage={"files": files}))
    ) as run:
        result = await CoverageAnalyzer(Path("/repo")).get_module_coverage()
    assert result == files
    assert run.await_args.args == (Path("/repo"), ["tests"])
    assert run.await_args.kwargs["coverage"] is True
    assert run.await_args.kwargs["timeout_sec"] == int(
        coverage_analyzer._CFG.collect_timeout_sec
    )


async def test_partial_run_still_returns_its_numbers() -> None:
    # Integration tests excluded by the service: the run is partial, the
    # numbers it measured are still the numbers.
    with patch(
        _SANDBOX,
        new=AsyncMock(
            return_value=_result(
                completeness="partial", coverage={"files": {"src/b.py": 10.0}}
            )
        ),
    ):
        assert await CoverageAnalyzer(Path("/repo")).get_module_coverage() == {
            "src/b.py": 10.0
        }


async def test_no_coverage_is_empty() -> None:
    for outcome in (
        _result(status="not_run", completeness="none", reason="down"),
        _result(coverage={"error": "No data to report."}),
    ):
        with patch(_SANDBOX, new=AsyncMock(return_value=outcome)):
            assert await CoverageAnalyzer(Path("/repo")).get_module_coverage() == {}
