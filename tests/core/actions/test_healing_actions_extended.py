# tests/core/actions/test_healing_actions_extended.py
"""
Tests for extended self-healing action handlers.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from body.actions.context import PlanExecutorContext
from body.actions.healing_actions_extended import (
    AddPolicyIDsHandler,
    EnforceLineLengthHandler,
    FixUnusedImportsHandler,
    RemoveDeadCodeHandler,
    SortImportsHandler,
)
from shared.models import TaskParams


@pytest.fixture
def mock_context(tmp_path):
    """Create a mock execution context."""
    context = MagicMock(spec=PlanExecutorContext)
    context.file_handler = MagicMock()
    context.file_handler.repo_path = tmp_path
    context.git_service = MagicMock()
    context.auditor_context = MagicMock()
    return context


@pytest.fixture
def mock_settings(tmp_path, mocker):
    """Mock settings with a test repo path."""
    # --- START OF FIX ---
    # Changed from "core.actions.healing_actions_extended.settings"
    mock_settings = mocker.patch("body.actions.healing_actions_extended.settings")
    # --- END OF FIX ---
    mock_settings.REPO_PATH = tmp_path
    return mock_settings


class TestFixUnusedImportsHandler:
    """Tests for FixUnusedImportsHandler."""

    def test_handler_name(self):
        """Test that handler has correct name."""
        handler = FixUnusedImportsHandler()
        assert handler.name == "autonomy.self_healing.fix_imports"

    @pytest.mark.asyncio
    # --- START OF FIX ---
    # Changed from "core.actions.healing_actions_extended.run_poetry_command"
    @patch("body.actions.healing_actions_extended.run_poetry_command")
    # --- END OF FIX ---
    async def test_execute_with_file_path(
        self, mock_run_poetry_command, mock_context, mock_settings
    ):
        """Test fixing imports for a specific file."""
        handler = FixUnusedImportsHandler()
        params = TaskParams(file_path="src/test.py")

        await handler.execute(params, mock_context)

        mock_run_poetry_command.assert_called_once()
        call_args = mock_run_poetry_command.call_args[0]
        assert "Fixing unused imports" in call_args[0]
        command_list = call_args[1]
        assert "ruff" in command_list
        assert "check" in command_list
        assert "--fix" in command_list
        assert "--select" in command_list
        assert "F401" in command_list
        assert "src/test.py" in command_list

    @pytest.mark.asyncio
    # --- START OF FIX ---
    # Changed from "core.actions.healing_actions_extended.run_poetry_command"
    @patch("body.actions.healing_actions_extended.run_poetry_command")
    # --- END OF FIX ---
    async def test_execute_without_file_path(
        self, mock_run_poetry_command, mock_context, mock_settings
    ):
        """Test fixing imports for entire src directory."""
        handler = FixUnusedImportsHandler()
        params = TaskParams()

        await handler.execute(params, mock_context)

        mock_run_poetry_command.assert_called_once()
        call_args = mock_run_poetry_command.call_args[0]
        assert "src/" in call_args[1]


class TestRemoveDeadCodeHandler:
    """Tests for RemoveDeadCodeHandler."""

    def test_handler_name(self):
        """Test that handler has correct name."""
        handler = RemoveDeadCodeHandler()
        assert handler.name == "autonomy.self_healing.remove_dead_code"

    @pytest.mark.asyncio
    # --- START OF FIX ---
    # Changed from "core.actions.healing_actions_extended.run_poetry_command"
    @patch("body.actions.healing_actions_extended.run_poetry_command")
    # --- END OF FIX ---
    async def test_execute(self, mock_run_poetry_command, mock_context, mock_settings):
        """Test removing dead code."""
        handler = RemoveDeadCodeHandler()
        params = TaskParams(file_path="src/test.py")

        await handler.execute(params, mock_context)

        mock_run_poetry_command.assert_called_once()
        call_args = mock_run_poetry_command.call_args[0]
        command_list = call_args[1]
        assert "ruff" in command_list
        assert "F401,F841" in command_list
        assert "src/test.py" in command_list


class TestEnforceLineLengthHandler:
    """Tests for EnforceLineLengthHandler."""

    def test_handler_name(self):
        """Test that handler has correct name."""
        handler = EnforceLineLengthHandler()
        assert handler.name == "autonomy.self_healing.fix_line_length"

    @pytest.mark.asyncio
    async def test_execute_with_file_path(self, mock_context, mock_settings, tmp_path):
        """Test fixing line lengths for a specific file."""
        handler = EnforceLineLengthHandler()
        test_file = tmp_path / "src" / "test.py"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("print('hello')")

        params = TaskParams(file_path="src/test.py")

        # PATCH THE ACTUAL MODULE WHERE THE FUNCTION IS DEFINED
        with patch(
            "features.self_healing.linelength_service._async_fix_line_lengths",
            new_callable=AsyncMock,
        ) as mock_fix:
            await handler.execute(params, mock_context)

            mock_fix.assert_awaited_once()
            call_args = mock_fix.call_args[0][0]
            assert len(call_args) == 1
            assert call_args[0].name == "test.py"

    @pytest.mark.asyncio
    async def test_execute_all_files(self, mock_context, mock_settings, tmp_path):
        """Test fixing line lengths for all files."""
        handler = EnforceLineLengthHandler()

        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "file1.py").write_text("print('a')")
        (src_dir / "file2.py").write_text("print('b')")

        params = TaskParams()

        # PATCH THE ACTUAL MODULE WHERE THE FUNCTION IS DEFINED
        with patch(
            "features.self_healing.linelength_service._async_fix_line_lengths",
            new_callable=AsyncMock,
        ) as mock_fix:
            await handler.execute(params, mock_context)

            mock_fix.assert_awaited_once()
            call_args = mock_fix.call_args[0][0]
            assert len(call_args) == 2


class TestAddPolicyIDsHandler:
    """Tests for AddPolicyIDsHandler."""

    def test_handler_name(self):
        """Test that handler has correct name."""
        handler = AddPolicyIDsHandler()
        assert handler.name == "autonomy.self_healing.add_policy_ids"

    @pytest.mark.asyncio
    async def test_execute(self, mock_context, mock_settings):
        """Test adding policy IDs."""
        handler = AddPolicyIDsHandler()
        params = TaskParams()

        # PATCH THE ACTUAL MODULE WHERE THE FUNCTION IS DEFINED
        with patch(
            "features.self_healing.policy_id_service.add_missing_policy_ids"
        ) as mock_add:
            mock_add.return_value = 5
            await handler.execute(params, mock_context)

            mock_add.assert_called_once_with(dry_run=False)


class TestSortImportsHandler:
    """Tests for SortImportsHandler."""

    def test_handler_name(self):
        """Test that handler has correct name."""
        handler = SortImportsHandler()
        assert handler.name == "autonomy.self_healing.sort_imports"

    @pytest.mark.asyncio
    # --- START OF FIX ---
    # Changed from "core.actions.healing_actions_extended.run_poetry_command"
    @patch("body.actions.healing_actions_extended.run_poetry_command")
    # --- END OF FIX ---
    async def test_execute(self, mock_run_poetry_command, mock_context, mock_settings):
        """Test sorting imports."""
        handler = SortImportsHandler()
        params = TaskParams(file_path="src/test.py")

        await handler.execute(params, mock_context)

        mock_run_poetry_command.assert_called_once()
        call_args = mock_run_poetry_command.call_args[0]
        command_list = call_args[1]
        assert "ruff" in command_list
        assert "--select" in command_list
        assert "I" in command_list
        assert "--fix" in command_list
