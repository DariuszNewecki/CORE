# tests/unit/test_git_service.py
from unittest.mock import MagicMock, call

import pytest

from services.git_service import GitService


@pytest.fixture
def mock_git_service(mocker, tmp_path):
    """Creates a GitService instance with a mocked subprocess.run."""
    (tmp_path / ".git").mkdir()

    mock_run = mocker.patch("subprocess.run")

    # Configure mock for the common flow: status -> add -A -> commit
    mock_run.side_effect = [
        MagicMock(stdout="?? new_file.py", stderr="", returncode=0),  # status
        MagicMock(stdout="", stderr="", returncode=0),  # add -A
        MagicMock(stdout="commit success", stderr="", returncode=0),  # commit
    ]

    service = GitService(repo_path=str(tmp_path))
    return service, mock_run


def test_git_add_all(mock_git_service):
    """Tests that add_all calls subprocess.run with correct arguments."""
    service, mock_run = mock_git_service
    mock_run.side_effect = None
    mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

    service.add_all()

    mock_run.assert_called_once_with(
        ["git", "add", "-A"],
        cwd=service.repo_path,
        capture_output=True,
        text=True,
        check=True,
    )


def test_git_commit(mock_git_service):
    """Tests that commit runs: add_all -> get_staged_files -> commit."""
    service, mock_run = mock_git_service
    commit_message = "feat(agent): Test commit"

    # Reset and configure mock for commit flow
    mock_run.side_effect = [
        MagicMock(stdout="", stderr="", returncode=0),  # add -A
        MagicMock(stdout="M  file.py", stderr="", returncode=0),  # diff --cached
        MagicMock(stdout="", stderr="", returncode=0),  # commit
    ]

    service.commit(commit_message)

    # Should call: add -A, diff --cached (for get_staged_files), commit
    assert mock_run.call_count == 3

    expected_calls = [
        call(
            ["git", "add", "-A"],
            cwd=service.repo_path,
            capture_output=True,
            text=True,
            check=True,
        ),
        call(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
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
    """Returns True when a .git directory exists."""
    (tmp_path / ".git").mkdir()
    service = GitService(repo_path=str(tmp_path))
    assert service.is_git_repo() is True


def test_is_git_repo_false(tmp_path):
    """Returns False if .git is missing (doesn't raise on init)."""
    service = GitService(repo_path=str(tmp_path))
    assert service.is_git_repo() is False
