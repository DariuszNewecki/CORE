"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/body/atomic/fix_actions.py
- Symbol: action_fix_logging
- Status: verified_in_sandbox
- Generated: 2026-01-11 02:55:05
"""

import pytest
from body.atomic.fix_actions import action_fix_logging
import time
from unittest.mock import Mock, AsyncMock

# The function returns ActionResult (async function)

@pytest.mark.asyncio
async def test_action_fix_logging_basic_operation():
    """Test basic operation with dry_run (write=False)."""
    mock_context = Mock()
    mock_context.file_handler = Mock()

    # Mock settings
    from body.atomic import fix_actions
    original_repo_path = fix_actions.settings.REPO_PATH
    fix_actions.settings.REPO_PATH = "/test/repo/path"

    # Mock LoggingFixer
    mock_fixer = Mock()
    mock_fixer.fix_all.return_value = {"fixed": 3, "errors": 0}

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(fix_actions, 'LoggingFixer', Mock(return_value=mock_fixer))
        mp.setattr(fix_actions, 'time', Mock(time=Mock(return_value=1000)))

        result = await action_fix_logging(mock_context, write=False)

    # Restore original
    fix_actions.settings.REPO_PATH = original_repo_path

    assert result.action_id == "fix.logging"
    assert result.ok is True
    assert result.data == {"fixed": 3, "errors": 0}
    assert result.duration_sec == 0.0

@pytest.mark.asyncio
async def test_action_fix_logging_with_write_true():
    """Test operation with write=True (not dry_run)."""
    mock_context = Mock()
    mock_context.file_handler = Mock()

    from body.atomic import fix_actions
    original_repo_path = fix_actions.settings.REPO_PATH
    fix_actions.settings.REPO_PATH = "/another/repo/path"

    mock_fixer = Mock()
    mock_fixer.fix_all.return_value = {"fixed": 5, "errors": 1}

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(fix_actions, 'LoggingFixer', Mock(return_value=mock_fixer))
        mp.setattr(fix_actions, 'time', Mock(time=Mock(side_effect=[2000, 2001])))

        result = await action_fix_logging(mock_context, write=True)

    fix_actions.settings.REPO_PATH = original_repo_path

    assert result.action_id == "fix.logging"
    assert result.ok is True
    assert result.data == {"fixed": 5, "errors": 1}
    assert result.duration_sec == 1.0

@pytest.mark.asyncio
async def test_action_fix_logging_verify_fixer_initialization():
    """Verify LoggingFixer is initialized with correct parameters."""
    mock_context = Mock()
    mock_context.file_handler = Mock()

    from body.atomic import fix_actions
    original_repo_path = fix_actions.settings.REPO_PATH
    fix_actions.settings.REPO_PATH = "/verified/repo/path"

    captured_args = []

    def capture_fixer_args(repo_root, file_handler, dry_run):
        captured_args.append({
            "repo_root": repo_root,
            "file_handler": file_handler,
            "dry_run": dry_run
        })
        mock_fixer = Mock()
        mock_fixer.fix_all.return_value = {"fixed": 1, "errors": 0}
        return mock_fixer

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(fix_actions, 'LoggingFixer', capture_fixer_args)
        mp.setattr(fix_actions, 'time', Mock(time=Mock(return_value=3000)))

        await action_fix_logging(mock_context, write=False)

    fix_actions.settings.REPO_PATH = original_repo_path

    assert len(captured_args) == 1
    assert captured_args[0]["repo_root"] == "/verified/repo/path"
    assert captured_args[0]["file_handler"] == mock_context.file_handler
    assert captured_args[0]["dry_run"] is True  # write=False means dry_run=True

@pytest.mark.asyncio
async def test_action_fix_logging_with_write_true_verify_dry_run():
    """Verify dry_run=False when write=True."""
    mock_context = Mock()
    mock_context.file_handler = Mock()

    from body.atomic import fix_actions
    original_repo_path = fix_actions.settings.REPO_PATH
    fix_actions.settings.REPO_PATH = "/test/path"

    captured_args = []

    def capture_fixer_args(repo_root, file_handler, dry_run):
        captured_args.append({
            "repo_root": repo_root,
            "file_handler": file_handler,
            "dry_run": dry_run
        })
        mock_fixer = Mock()
        mock_fixer.fix_all.return_value = {"fixed": 2, "errors": 0}
        return mock_fixer

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(fix_actions, 'LoggingFixer', capture_fixer_args)
        mp.setattr(fix_actions, 'time', Mock(time=Mock(side_effect=[4000, 4000.5])))

        await action_fix_logging(mock_context, write=True)

    fix_actions.settings.REPO_PATH = original_repo_path

    assert captured_args[0]["dry_run"] is False  # write=True means dry_run=False

@pytest.mark.asyncio
async def test_action_fix_logging_with_additional_kwargs():
    """Test that additional kwargs are accepted (should be ignored by function)."""
    mock_context = Mock()
    mock_context.file_handler = Mock()

    from body.atomic import fix_actions
    original_repo_path = fix_actions.settings.REPO_PATH
    fix_actions.settings.REPO_PATH = "/kwargs/test"

    mock_fixer = Mock()
    mock_fixer.fix_all.return_value = {"fixed": 0, "errors": 0}

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(fix_actions, 'LoggingFixer', Mock(return_value=mock_fixer))
        mp.setattr(fix_actions, 'time', Mock(time=Mock(return_value=5000)))

        # Pass additional kwargs that should be ignored
        result = await action_fix_logging(
            mock_context,
            write=False,
            extra_param="value",
            another_param=123
        )

    fix_actions.settings.REPO_PATH = original_repo_path

    assert result.action_id == "fix.logging"
    assert result.ok is True

@pytest.mark.asyncio
async def test_action_fix_logging_duration_calculation():
    """Verify duration calculation is correct."""
    mock_context = Mock()
    mock_context.file_handler = Mock()

    from body.atomic import fix_actions
    original_repo_path = fix_actions.settings.REPO_PATH
    fix_actions.settings.REPO_PATH = "/duration/test"

    mock_fixer = Mock()
    mock_fixer.fix_all.return_value = {"fixed": 1, "errors": 0}

    time_values = [6000.0, 6002.5]  # 2.5 second difference

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(fix_actions, 'LoggingFixer', Mock(return_value=mock_fixer))
        mp.setattr(fix_actions, 'time', Mock(time=Mock(side_effect=time_values)))

        result = await action_fix_logging(mock_context, write=False)

    fix_actions.settings.REPO_PATH = original_repo_path

    assert result.duration_sec == 2.5
