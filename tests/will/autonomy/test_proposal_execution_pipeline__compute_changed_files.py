# tests/will/autonomy/test_proposal_execution_pipeline__compute_changed_files.py
"""Unit tests for compute_changed_files (ADR-129 GitService delegation).

P3-#15 instrument — covers the asyncio.create_subprocess_exec removal
shipped in f6f530a2. compute_changed_files now delegates entirely to
GitService.diff_file_names; these tests verify every branch of that
delegation without touching git.

All tests are synchronous-async, no DB, no filesystem.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from will.autonomy.proposal_execution_pipeline import compute_changed_files


async def test_returns_empty_when_git_service_is_none() -> None:
    result = await compute_changed_files(None, "abc", "def", "prop-1")
    assert result == []


async def test_returns_empty_when_pre_sha_is_none() -> None:
    git_service = MagicMock()
    result = await compute_changed_files(git_service, None, "def", "prop-1")
    assert result == []
    git_service.diff_file_names.assert_not_called()


async def test_returns_empty_when_post_sha_is_empty_string() -> None:
    git_service = MagicMock()
    result = await compute_changed_files(git_service, "abc", "", "prop-1")
    assert result == []
    git_service.diff_file_names.assert_not_called()


async def test_returns_file_list_from_diff_file_names() -> None:
    git_service = MagicMock()
    git_service.diff_file_names = AsyncMock(return_value=["src/a.py", "src/b.py"])
    result = await compute_changed_files(git_service, "abc", "def", "prop-1")
    assert result == ["src/a.py", "src/b.py"]
    git_service.diff_file_names.assert_awaited_once_with("abc", "def")


async def test_returns_empty_when_diff_file_names_returns_none() -> None:
    git_service = MagicMock()
    git_service.diff_file_names = AsyncMock(return_value=None)
    result = await compute_changed_files(git_service, "abc", "def", "prop-1")
    assert result == []


async def test_returns_empty_and_does_not_raise_when_diff_raises() -> None:
    git_service = MagicMock()
    git_service.diff_file_names = AsyncMock(side_effect=RuntimeError("git exploded"))
    result = await compute_changed_files(git_service, "abc", "def", "prop-1")
    assert result == []


async def test_returns_empty_list_not_none() -> None:
    """Return type is always list[str], never None, even on all-None inputs."""
    result = await compute_changed_files(None, None, None, "prop-x")
    assert isinstance(result, list)
