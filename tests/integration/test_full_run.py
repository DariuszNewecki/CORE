# tests/integration/test_full_run.py
"""
An end-to-end integration test for the CORE system.
This test simulates a real user request and verifies the entire
Plan -> Generate -> Execute cycle with the new agent architecture.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from core.main import app
from fastapi.testclient import TestClient


@pytest.fixture
def mock_agents(mocker):
    """Mocks the PlannerAgent and ExecutionAgent."""
    # Mock Planner to return a valid plan
    mock_plan = [
        MagicMock(
            step="Create a simple Python file.",
            action="create_file",
            params=MagicMock(file_path="src/hello.py", code=None),
        )
    ]
    mocker.patch("core.main.PlannerAgent.create_execution_plan", return_value=mock_plan)

    # Mock ExecutionAgent to succeed
    mocker.patch(
        "core.main.ExecutionAgent.execute_plan", new_callable=AsyncMock
    ).return_value = (True, "Plan executed successfully.")


@pytest.fixture
def test_git_repo(tmp_path: Path):
    """Creates a temporary, valid Git repository for the test to run in."""
    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    (tmp_path / "src").mkdir()
    return tmp_path


def test_execute_goal_end_to_end(mock_agents, test_git_repo, monkeypatch, mocker):
    """Tests the entire /execute_goal endpoint flow with the refactored agents."""
    monkeypatch.chdir(test_git_repo)

    # We still need to mock the services that are initialized in main.py
    mocker.patch("core.main.OrchestratorClient")
    mocker.patch("core.main.GeneratorClient")
    mocker.patch("core.main.GitService")
    mocker.patch("core.main.IntentGuard")

    with TestClient(app) as client:
        response = client.post(
            "/execute_goal", json={"goal": "Create a hello world script"}
        )

        assert response.status_code == 200
        assert response.json()["status"] == "success"
