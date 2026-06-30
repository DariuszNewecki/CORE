"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/body/atomic/fix_actions.py
- Symbol: action_format_code
- Status: 6 tests passed, some failed
- Passing tests: test_action_format_code_basic, test_action_format_code_with_write, test_action_format_code_explicit_false, test_action_format_code_duration_calculation, test_action_format_code_always_true_formatted, test_action_format_code_format_code_called
- Generated: 2026-01-11 02:52:15
- Hand-fixed 2026-05-25 for issue #447: dropped time.time mocking after the
  runtime path added an extra logger.debug LogRecord (via YAMLProcessor's
  lazy config load) that exhausted the 3-element side_effect lists. Uses the
  real clock and asserts duration_sec >= 0 instead — matches the pattern in
  test_fix_actions__action_fix_placeholders.py.
"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


from body.atomic.fix_actions import action_format_code
from shared.governance_token import authorize_execution


async def test_action_format_code_basic():
    """Test basic formatting without writing."""
    with patch("body.self_healing.code_style_service.format_code") as mock_format:
        with authorize_execution("format.code"):
            result = await action_format_code(write=False)
        mock_format.assert_called_once()
        assert result.action_id == "fix.format"
        assert result.ok
        assert result.data == {"formatted": True, "write": False}
        assert isinstance(result.duration_sec, float)
        assert result.duration_sec >= 0


async def test_action_format_code_with_write():
    """Test formatting with write=True."""
    with patch("body.self_healing.code_style_service.format_code") as mock_format:
        with authorize_execution("format.code"):
            result = await action_format_code(write=True)
        mock_format.assert_called_once()
        assert result.action_id == "fix.format"
        assert result.ok
        assert result.data == {"formatted": True, "write": True}
        assert isinstance(result.duration_sec, float)
        assert result.duration_sec >= 0


async def test_action_format_code_explicit_false():
    """Test with explicit write=False parameter."""
    with patch("body.self_healing.code_style_service.format_code") as mock_format:
        with authorize_execution("format.code"):
            result = await action_format_code(write=False)
        mock_format.assert_called_once()
        assert not result.data["write"]


async def test_action_format_code_duration_calculation():
    """Verify duration_sec is a non-negative float."""
    with patch("body.self_healing.code_style_service.format_code"):
        with authorize_execution("format.code"):
            result = await action_format_code(write=False)
        assert isinstance(result.duration_sec, float)
        assert result.duration_sec >= 0


async def test_action_format_code_always_true_formatted():
    """Verify formatted is always True in data."""
    with patch("body.self_healing.code_style_service.format_code"):
        with authorize_execution("format.code"):
            result = await action_format_code(write=False)
        assert result.data["formatted"]


async def test_action_format_code_format_code_called():
    """Verify format_code() is always called exactly once."""
    with patch("body.self_healing.code_style_service.format_code") as mock_format:
        with authorize_execution("format.code"):
            await action_format_code(write=False)
        # No core_context → cwd falls back to None (process cwd, CLI default).
        mock_format.assert_called_once_with(path=None, write=False, cwd=None)


async def test_action_format_code_threads_worktree_cwd():
    """#638: a scoped core_context routes ruff's cwd into the flow worktree.

    When the action runs inside a hermetic flow worktree (ADR-106), the
    injected core_context's git_service.repo_path points at the sandbox.
    format_code MUST receive that path as cwd so ruff reformats the sandbox
    tree, not the real one — otherwise the working tree is polluted.
    """
    worktree = Path("/var/tmp/core-action-sandbox-deadbeef")
    core_context = SimpleNamespace(git_service=SimpleNamespace(repo_path=worktree))
    with patch("body.self_healing.code_style_service.format_code") as mock_format:
        with authorize_execution("format.code"):
            result = await action_format_code(core_context=core_context, write=True)
        mock_format.assert_called_once_with(path=None, write=True, cwd=worktree)
        assert result.ok
