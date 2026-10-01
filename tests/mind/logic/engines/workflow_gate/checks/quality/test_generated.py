from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch


# ID: f3b8887e-3ee7-4661-9d9e-6d0ac3a46522
def test_QualityGateCheck() -> None:
    import asyncio
    from pathlib import Path

    from mind.logic.engines.workflow_gate.checks.quality import QualityGateCheck

    path_resolver = MagicMock()
    path_resolver.repo_root = Path("/repo")

    check = QualityGateCheck(path_resolver, "mypy_check", ["mypy", "."])

    mock_process = MagicMock()
    mock_process.returncode = 1
    mock_process.communicate = AsyncMock(
        return_value=(b"src/foo.py:12: error: Incompatible types", b"")
    )

    with patch(
        "mind.logic.engines.workflow_gate.checks.quality.asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=mock_process),
    ) as mock_exec:
        result = asyncio.run(check.verify(None, {}))

    assert isinstance(result, list)
    assert len(result) == 1
    violation = result[0]
    assert violation.file_path == "src/foo.py"
    assert violation.context["tool"] == "mypy"
    assert violation.context["issue_count"] == 1
    mock_exec.assert_awaited_once()
