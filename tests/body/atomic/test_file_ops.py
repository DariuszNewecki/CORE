"""Tests for file.create and file.edit atomic actions (src/body/atomic/file_ops.py).

Pins the audit-identity contract: each action must return its own action_id,
never the other's. Regression for the nested-delegation bug where file.edit
called action_create_file() directly and returned action_id="file.create".
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from body.atomic.file_ops import action_create_file, action_edit_file
from shared.governance_token import authorize_execution


def _make_context(*, is_git_repo: bool = False) -> SimpleNamespace:
    file_handler = MagicMock()
    git_service = MagicMock()
    git_service.is_git_repo.return_value = is_git_repo
    return SimpleNamespace(file_handler=file_handler, git_service=git_service)


# ---------------------------------------------------------------------------
# Audit identity — the core regression contract
# ---------------------------------------------------------------------------


# ID: e48d65b5-fa1f-4e6b-a343-125699350a8d
@pytest.mark.asyncio
async def test_action_create_file_returns_file_create_action_id() -> None:
    """file.create must return action_id='file.create', never 'file.edit'."""
    ctx = _make_context()
    with authorize_execution("file.create"):
        result = await action_create_file(
            file_path="src/foo.txt", code="hello", core_context=ctx, write=False
        )
    assert result.action_id == "file.create"


# ID: 00216939-85c4-4556-a20f-48eef1914e5d
@pytest.mark.asyncio
async def test_action_edit_file_returns_file_edit_action_id() -> None:
    """file.edit must return action_id='file.edit', never 'file.create'."""
    ctx = _make_context()
    with authorize_execution("file.edit"):
        result = await action_edit_file(
            file_path="src/foo.txt", code="hello", core_context=ctx, write=False
        )
    assert result.action_id == "file.edit"


# ---------------------------------------------------------------------------
# Syntax validation — shared gate, identity preserved on failure
# ---------------------------------------------------------------------------


# ID: b7ebd01e-124d-4566-b244-fb2babebbe32
@pytest.mark.asyncio
async def test_action_create_file_syntax_error_preserves_action_id() -> None:
    """Syntax failure from file.create must still carry action_id='file.create'."""
    ctx = _make_context()
    with authorize_execution("file.create"):
        result = await action_create_file(
            file_path="src/bad.py", code="def (:", core_context=ctx, write=False
        )
    assert not result.ok
    assert result.action_id == "file.create"
    assert "Syntax Error" in result.data["error"]


# ID: ad52dd3f-43d9-473e-aebf-791dcbb12ebe
@pytest.mark.asyncio
async def test_action_edit_file_syntax_error_preserves_action_id() -> None:
    """Syntax failure from file.edit must still carry action_id='file.edit'."""
    ctx = _make_context()
    with authorize_execution("file.edit"):
        result = await action_edit_file(
            file_path="src/bad.py", code="def (:", core_context=ctx, write=False
        )
    assert not result.ok
    assert result.action_id == "file.edit"
    assert "Syntax Error" in result.data["error"]


# ---------------------------------------------------------------------------
# Write routing — FileHandler called, result identity correct
# ---------------------------------------------------------------------------


# ID: 9f7aabb1-5a64-47e6-90fa-aa44f0c89455
@pytest.mark.asyncio
async def test_action_edit_file_write_true_calls_file_handler() -> None:
    """file.edit with write=True routes through FileHandler and returns ok result."""
    ctx = _make_context(is_git_repo=False)
    with authorize_execution("file.edit"):
        result = await action_edit_file(
            file_path="src/foo.txt", code="content", core_context=ctx, write=True
        )
    ctx.file_handler.write_runtime_text.assert_called_once_with(
        "src/foo.txt", "content"
    )
    assert result.ok
    assert result.action_id == "file.edit"
    assert result.data["written"] is True


# ID: ee7e5eee-4df3-4d19-8a59-221125ef59e3
@pytest.mark.asyncio
async def test_action_create_file_dry_run_does_not_call_file_handler() -> None:
    """file.create with write=False must not touch FileHandler."""
    ctx = _make_context()
    with authorize_execution("file.create"):
        result = await action_create_file(
            file_path="src/foo.txt", code="content", core_context=ctx, write=False
        )
    ctx.file_handler.write_runtime_text.assert_not_called()
    assert result.ok
    assert result.action_id == "file.create"
    assert result.data["written"] is False
