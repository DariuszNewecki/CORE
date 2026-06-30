"""Tests for action_fix_imports (fix.imports) worktree-cwd threading.

#638: fix.imports ran ruff via run_poetry_command with no cwd, so the
subprocess inherited the daemon's process cwd (the real repo) even when the
action executed inside a hermetic flow worktree (ADR-106). These tests pin
the contract that the injected core_context's repo_path is threaded as the
subprocess cwd, and that the legacy no-context path still falls back to None.
"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


from body.atomic.fix_actions import action_fix_imports
from shared.governance_token import authorize_execution


async def test_action_fix_imports_no_context_uses_process_cwd():
    """No core_context → run_poetry_command receives cwd=None (CLI default)."""
    with patch("shared.utils.subprocess_utils.run_poetry_command") as mock_run:
        with authorize_execution("fix.imports"):
            result = await action_fix_imports(write=True)
        assert result.ok
        _, kwargs = mock_run.call_args
        assert kwargs.get("cwd") is None


async def test_action_fix_imports_threads_worktree_cwd():
    """#638: a scoped core_context routes ruff's cwd into the flow worktree."""
    worktree = Path("/var/tmp/core-action-sandbox-deadbeef")
    core_context = SimpleNamespace(git_service=SimpleNamespace(repo_path=worktree))
    with patch("shared.utils.subprocess_utils.run_poetry_command") as mock_run:
        with authorize_execution("fix.imports"):
            result = await action_fix_imports(core_context=core_context, write=True)
        assert result.ok
        _, kwargs = mock_run.call_args
        assert kwargs.get("cwd") == worktree
