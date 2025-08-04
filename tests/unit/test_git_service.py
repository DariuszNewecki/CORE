# tests/unit/test_git_service.py
import pytest
from unittest.mock import MagicMock
from pathlib import Path
# --- FIX: Changed import from 'src.core.git_service' to 'core.git_service' ---
from core.git_service import GitService

@pytest.fixture
def mock_git_service(mocker, tmp_path):
    """Creates a GitService instance with a mocked subprocess.run."""
    (tmp_path / ".git").mkdir()
    
    mock_run = mocker.patch("subprocess.run")
    # Configure the mock to return a value that can be stripped
    mock_run.return_value = MagicMock(stdout="mock_commit_hash\n", stderr="", returncode=0, check_returncode=None)
    
    service = GitService(repo_path=str(tmp_path))
    return service, mock_run

def test_git_commit(mock_git_service):
    """Tests that the commit method calls subprocess.run with the correct arguments."""
    service, mock_run = mock_git_service
    commit_message = "feat(agent): Test commit"

    service.commit(commit_message)

    # The commit method only calls subprocess.run once
    mock_run.assert_called_once()
    commit_call_args = mock_run.call_args.args[0]
    assert commit_call_args == ['git', 'commit', '-m', commit_message]