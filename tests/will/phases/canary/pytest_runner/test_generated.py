from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from will.phases.canary.pytest_runner import PytestRunner


# ID: 110ee45a-5c85-4d88-8ab8-415ad271f9af
def test_PytestRunner_run_tests() -> None:
    import asyncio

    path_resolver = MagicMock()
    path_resolver.repo_root = "/repo"

    runner = PytestRunner(path_resolver=path_resolver, execution_timeout=30)

    result = MagicMock()
    result.status = "passed"
    result.completeness = "full"
    result.ok = True
    result.exit_code = 0
    result.reason = ""
    result.stdout = "all good"
    result.stderr = ""
    result.failed_ids = []
    result.counts = {"passed": 5, "failed": 0}

    with patch(
        "will.phases.canary.pytest_runner.run_in_sandbox",
        new=AsyncMock(return_value=result),
    ) as mock_run:
        out = asyncio.run(runner.run_tests(["tests/test_a.py"]))

    mock_run.assert_awaited_once_with("/repo", ["tests/test_a.py"], timeout_sec=30)
    assert out["passed"] == 5
    assert out["failed"] == 0
    assert out["exit_code"] == 0
    assert "all good" in out["output"]
