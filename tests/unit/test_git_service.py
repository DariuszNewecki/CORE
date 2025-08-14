# tests/unit/test_git_service.py
from unittest.mock import MagicMock, call

import pytest
from core.git_service import GitService


@pytest.fixture
def mock_git_service(mocker, tmp_path):
    """Creates a GitService instance with a mocked subprocess.run."""
    (tmp_path / ".git").mkdir()

    mock_run = mocker.patch("subprocess.run")

    # Configure mock for multiple calls: first for status, then for commit
    mock_run.side_effect = [
        MagicMock(stdout=" M my_file.py", stderr="", returncode=0),  # For git status
        MagicMock(stdout="commit success", stderr="", returncode=0),  # For git commit
    ]

    service = GitService(repo_path=str(tmp_path))
    return service, mock_run


def test_git_add(mock_git_service):
    """Tests that the add method calls subprocess.run with the correct arguments."""
    service, mock_run = mock_git_service
    # Reset side_effect for this simple, single-call test
    mock_run.side_effect = None
    mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

    file_to_add = "src/core/main.py"
    service.add(file_to_add)

    mock_run.assert_called_once_with(
        ["git", "add", file_to_add],
        cwd=service.repo_path,
        capture_output=True,
        text=True,
        check=True,
    )


def test_git_commit(mock_git_service):
    """Tests that the commit method calls subprocess.run with status and then commit."""
    service, mock_run = mock_git_service
    commit_message = "feat(agent): Test commit"

    service.commit(commit_message)

    # --- THIS IS THE FIX ---
    # Assert that run was called twice
    assert mock_run.call_count == 2

    # Check the calls were made in the correct order with correct arguments
    expected_calls = [
        call(
            ["git", "status", "--porcelain"],
            cwd=service.repo_path,
            capture_output=True,
            text=True,
            check=True,
        ),
        call(
            ["git", "commit", "-m", commit_message],
            cwd=service.repo_path,
            capture_output=True,
            text=True,
            check=True,
        ),
    ]
    mock_run.assert_has_calls(expected_calls)


def test_is_git_repo_true(tmp_path):
    """Tests that is_git_repo returns True when a .git directory exists."""
    (tmp_path / ".git").mkdir()
    service = GitService(repo_path=str(tmp_path))
    assert service.is_git_repo() is True


def test_is_git_repo_false(tmp_path):
    """Tests that GitService raises an error if .git directory is missing on init."""
    with pytest.raises(ValueError):
        GitService(repo_path=str(tmp_path))
