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


from pathlib import Path

from mind.logic.engines.workflow_gate.checks.quality import QualityGateCheck


# ID: b8c12e00-5afc-43f3-a5c6-1b8369b386ec
def test_QualityGateCheck_verify():
    path_resolver = MagicMock()
    path_resolver.repo_root = Path("/repo")

    check = QualityGateCheck(path_resolver, "lint", ["ruff", "check"])

    fake_process = MagicMock()
    fake_process.returncode = 0
    fake_process.communicate = AsyncMock(return_value=(b"", b""))

    with patch(
        "mind.logic.engines.workflow_gate.checks.quality.asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=fake_process),
    ):
        import asyncio

        result = asyncio.run(check.verify(None, {}))

    assert result == []
    fake_process.communicate.assert_awaited_once()


import pytest


@pytest.mark.asyncio
# ID: 62ae83d8-3e12-461e-a8d9-aad42b66adb1
async def test_QualityGateCheck_verify():
    path_resolver = MagicMock()
    path_resolver.repo_root = Path("/tmp/repo")

    check = QualityGateCheck(path_resolver, "lint", ["echo", "ok"])

    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.communicate = AsyncMock(return_value=(b"", b""))

    with patch(
        "asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=mock_process),
    ):
        result = await check.verify(None, {})

    assert list(result) == []
    mock_process.communicate.assert_awaited_once()


# ID: bf2a81e2-c09b-4c2d-8920-9fb0c2f3cc2b
async def test_QualityGateCheck_verify() -> None:
    path_resolver = MagicMock()
    path_resolver.repo_root = "/repo"

    check = QualityGateCheck(
        path_resolver=path_resolver,
        check_type="pytest_check",
        cmd=["pytest", "--check"],
    )

    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.communicate = AsyncMock(return_value=(b"", b""))

    with patch(
        "mind.logic.engines.workflow_gate.checks.quality.asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=mock_process),
    ) as mock_exec:
        result = await check.verify(None, {})

    assert result == []
    mock_exec.assert_awaited_once()
    mock_process.communicate.assert_awaited_once()


import asyncio


# ID: a17cf77c-f7f0-4f0f-92fd-6f2e37086938
def test_QualityGateCheck_verify():
    path_resolver = MagicMock()
    path_resolver.repo_root = Path("/repo")

    check = QualityGateCheck(path_resolver, "lint", ["echo", "ok"])

    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.communicate = AsyncMock(return_value=(b"", b""))

    with patch(
        "mind.logic.engines.workflow_gate.checks.quality.asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=mock_process),
    ):
        result = asyncio.run(check.verify(None, {}))

    assert result == []
    mock_process.communicate.assert_awaited_once()


async def _run(check: QualityGateCheck):
    return await check.verify(file_path=None, params={})


# ID: 3061a000-bcd9-4d20-907b-071262334579
def test_QualityGateCheck_verify() -> None:
    path_resolver = MagicMock()
    path_resolver.repo_root = Path("/tmp/repo")
    check = QualityGateCheck(
        path_resolver=path_resolver, check_type="ruff", cmd=["ruff", "check"]
    )

    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.communicate = AsyncMock(return_value=(b"", b""))

    with patch(
        "mind.logic.engines.workflow_gate.checks.quality.asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=mock_process),
    ):
        result = asyncio.run(_run(check))

    assert list(result) == []





# ID: fd2fddc0-e8c4-49fe-a808-3cc80cb98354
async def test_QualityGateCheck_verify() -> None:
    path_resolver = MagicMock()
    path_resolver.repo_root = Path("/tmp/repo")

    check = QualityGateCheck(
        path_resolver=path_resolver,
        check_type="lint",
        cmd=["ruff", "check"],
    )

    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.communicate = AsyncMock(return_value=(b"", b""))

    with patch(
        "mind.logic.engines.workflow_gate.checks.quality.asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=mock_process),
    ):
        result = await check.verify(file_path=None, params={})

    assert result == []
    mock_process.communicate.assert_awaited_once()
