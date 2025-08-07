# tests/unit/test_git_service.py
import pytest
from unittest.mock import MagicMock, call
from pathlib import Path
from core.git_service import GitService

@pytest.fixture
def mock_git_service(mocker, tmp_path):
    """Creates a GitService instance with a mocked subprocess.run."""
    # Simulate a real git repo
    (tmp_path / ".git").mkdir()
    
    # Mock the subprocess.run function
    mock_run = mocker.patch("subprocess.run")
    
    # Configure the mock to return a completed process object
    mock_run.return_value = MagicMock(
        stdout="mock_output\n", 
        stderr="", 
        returncode=0,
        check_returncode=lambda: None  # Mock check_returncode to do nothing
    )
    
    service = GitService(repo_path=str(tmp_path))
    return service, mock_run

def test_git_add(mock_git_service):
    """Tests that the add method calls subprocess.run with the correct arguments."""
    service, mock_run = mock_git_service
    file_to_add = "src/core/main.py"

    service.add(file_to_add)

    # Verify that 'git add' was called with the correct file path
    mock_run.assert_called_once_with(
        ['git', 'add', file_to_add],
        cwd=service.repo_path,
        capture_output=True,
        text=True,
        check=True
    )

def test_git_commit(mock_git_service):
    """Tests that the commit method calls subprocess.run with the correct arguments."""
    service, mock_run = mock_git_service
    commit_message = "feat(agent): Test commit"

    service.commit(commit_message)

    # The commit method only calls subprocess.run once
    mock_run.assert_called_once()
    
    # Check the arguments of the call
    args, kwargs = mock_run.call_args
    assert args[0] == ['git', 'commit', '-m', commit_message]
    assert kwargs['cwd'] == service.repo_path

def test_is_git_repo_true(tmp_path):
    """Tests that is_git_repo returns True when a .git directory exists."""
    (tmp_path / ".git").mkdir()
    service = GitService(repo_path=str(tmp_path))
    assert service.is_git_repo() is True

def test_is_git_repo_false(tmp_path):
    """Tests that GitService raises an error if .git directory is missing on init."""
    with pytest.raises(ValueError):
        GitService(repo_path=str(tmp_path))