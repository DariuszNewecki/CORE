# tests/integration/test_full_run.py
"""
An end-to-end integration test for the CORE system.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from core.main import app


@pytest.fixture
def mock_cognitive_service(mocker):
    """Mocks the CognitiveService to return mock clients."""
    mock_service = MagicMock()
    # Configure the mock to return a mock client when get_client_for_role is called
    mock_client = MagicMock()
    mock_client.make_request.return_value = json.dumps(
        [
            {
                "step": "Create a simple Python file.",
                "action": "create_file",
                "params": {"file_path": "src/hello.py"},
            }
        ]
    )
    mock_service.get_client_for_role.return_value = mock_client
    mocker.patch("agents.development_cycle.CognitiveService", return_value=mock_service)


@pytest.fixture
def test_git_repo(tmp_path: Path):
    """Creates a temporary, valid Git repository for the test to run in."""
    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    (tmp_path / "src").mkdir()
    intent_dir = tmp_path / ".intent"
    (intent_dir / "policies").mkdir(parents=True)
    (intent_dir / "policies" / "agent_behavior_policy.yaml").write_text(
        "planner_agent:\n  max_retries: 1\n  task_timeout: 30"
    )
    return tmp_path


def test_execute_goal_end_to_end(
    mock_cognitive_service, test_git_repo, monkeypatch, mocker
):
    """Tests the /execute_goal endpoint with a mocked cognitive service."""
    monkeypatch.chdir(test_git_repo)

    # We still need to mock the execution part to avoid actual file writes
    mocker.patch(
        "agents.development_cycle.ExecutionAgent.execute_plan", new_callable=AsyncMock
    ).return_value = (True, "Plan executed successfully.")

    with TestClient(app) as client:
        response = client.post(
            "/execute_goal", json={"goal": "Create a hello world script"}
        )

        assert response.status_code == 200
        assert response.json()["status"] == "success"
