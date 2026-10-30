from __future__ import annotations

from unittest.mock import MagicMock, patch

from will.phases.code_generation.work_directory_manager import WorkDirectoryManager


# ID: eb31e215-9855-432f-bdc0-39239ada7843
def test_WorkDirectoryManager_create_session_directory():
    file_service = MagicMock()
    manager = WorkDirectoryManager(file_service=file_service)

    manager._create_safe_slug = MagicMock(return_value="refactor_cli")

    with patch(
        "will.phases.code_generation.work_directory_manager.datetime"
    ) as mock_datetime:
        mock_datetime.now.return_value.strftime.return_value = "20260118_120534"

        result = manager.create_session_directory("Refactor CLI")

    assert result == "work/code_generation/20260118_120534_refactor_cli"
    file_service.ensure_dir.assert_called_once_with(
        "work/code_generation/20260118_120534_refactor_cli"
    )
    manager._create_safe_slug.assert_called_once_with("Refactor CLI")
