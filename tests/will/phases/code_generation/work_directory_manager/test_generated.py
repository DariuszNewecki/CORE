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





# ID: 6ec80288-99a0-492c-b1aa-e0c5bd148594
def test_WorkDirectoryManager():
    file_service = MagicMock()
    dir_path = "work/code_generation/20260118_120534_refactor_cli"
    file_service.ensure_dir = MagicMock(return_value=dir_path)

    manager = WorkDirectoryManager(file_service=file_service)

    result = manager.create_session_directory(goal="Refactor CLI")

    assert isinstance(result, str)
    assert result.startswith("work/code_generation/")
    assert "refactor_cli" in result
    file_service.ensure_dir.assert_called_once_with(result)
