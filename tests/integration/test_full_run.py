# tests/integration/test_full_run.py
"""
An end-to-end integration test for the CORE system.
This test simulates a real user request and verifies the entire
Plan -> Generate -> Validate -> Write -> Commit cycle.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from core.main import app
from fastapi.testclient import TestClient


# Use pytest-mock to simplify mocking
@pytest.fixture
def mock_llm_clients(mocker):
    """Mocks both the Orchestrator and Generator LLM clients."""
    # Mock the Orchestrator to return a valid plan
    mock_orchestrator = mocker.patch("core.main.OrchestratorClient", autospec=True)
    plan_json = json.dumps(
        [
            {
                "step": "Create a simple Python file.",
                "action": "create_file",
                "params": {"file_path": "src/hello.py"},
            }
        ]
    )
    mock_orchestrator.return_value.make_request.return_value = (
        f"```json\n{plan_json}\n```"
    )

    # Mock the Generator to return valid Python code
    mock_generator = mocker.patch("core.main.GeneratorClient", autospec=True)
    # --- THIS IS THE FIX (Part 1 of 2) ---
    # We now mock the unformatted code, just like a real LLM would produce.
    mock_generator.return_value.make_request.return_value = "print('Hello from CORE!')"

    return mock_orchestrator, mock_generator


@pytest.fixture
def test_git_repo(tmp_path: Path):
    """Creates a temporary, valid Git repository for the test to run in."""
    import subprocess

    # Initialize a git repo in the temp directory
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    # Create the necessary src directory
    (tmp_path / "src").mkdir()
    return tmp_path


def test_execute_goal_end_to_end(mock_llm_clients, test_git_repo, monkeypatch, mocker):
    """
    Tests the entire /execute_goal endpoint flow.
    - Mocks LLM responses.
    - Runs against a real temporary file system with a Git repo.
    - Asserts that the file is created with the correct content.
    - Asserts that a Git commit was made.
    """
    # Use monkeypatch to change the current working directory for the test
    monkeypatch.chdir(test_git_repo)

    # Mock the GitService to track commit calls
    mock_git_service_instance = MagicMock()
    mock_git_service_instance.is_git_repo.return_value = True
    mocker.patch("core.main.GitService", return_value=mock_git_service_instance)

    with TestClient(app) as client:
        # 1. Make the API call
        response = client.post(
            "/execute_goal", json={"goal": "Create a hello world script"}
        )

        # 2. Assert the API response is successful
        assert response.status_code == 200
        assert response.json()["status"] == "success"

        # 3. Assert the file was created correctly
        expected_file = test_git_repo / "src" / "hello.py"
        assert expected_file.exists()

        # --- THIS IS THE FIX (Part 2 of 2) ---
        # Assert that the file content matches what the code formatter (black)
        # would produce: double quotes and a trailing newline.
        expected_content = 'print("Hello from CORE!")\n'
        assert expected_file.read_text() == expected_content

        # 4. Assert that the Git commit was made
        mock_git_service_instance.commit.assert_called_once()
        commit_message = mock_git_service_instance.commit.call_args[0][0]
        assert "Create new file src/hello.py" in commit_message
