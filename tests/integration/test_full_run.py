# tests/integration/test_full_run.py
"""
An end-to-end integration test for the CORE system.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from core.main import app


@pytest.fixture
def mock_cognitive_service(mocker):
    """Mocks the CognitiveService to return mock clients."""
    mock_service = MagicMock()
    mock_client = MagicMock()
    mock_client.make_request.return_value = json.dumps(
        [
            {
                "step": "Create a simple Python file.",
                "action": "create_file",
                "params": {"file_path": "src/hello.py", "code": "print('hello')"},
            }
        ]
    )
    mock_service.get_client_for_role.return_value = mock_client
    mocker.patch("agents.development_cycle.CognitiveService", return_value=mock_service)
    mocker.patch("core.main.CognitiveService", return_value=mock_service)


@pytest.fixture
def test_git_repo(tmp_path: Path):
    """Creates a temporary, valid Git repository for the test to run in."""
    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    (tmp_path / "src").mkdir()
    intent_dir = tmp_path / ".intent"

    # --- THIS IS THE FIX ---
    # Create all required constitutional files for the development cycle to run.
    (intent_dir / "policies").mkdir(parents=True)
    (intent_dir / "policies" / "agent_behavior_policy.yaml").write_text(
        "planner_agent:\n  max_retries: 1\n  task_timeout: 30"
    )

    (intent_dir / "knowledge").mkdir(parents=True)
    (intent_dir / "knowledge" / "cognitive_roles.yaml").write_text(
        "cognitive_roles: []"
    )
    (intent_dir / "knowledge" / "resource_manifest.yaml").write_text(
        "llm_resources: []"
    )

    (intent_dir / "prompts").mkdir(parents=True)
    (intent_dir / "prompts" / "planner_agent.prompt").write_text("Goal: {goal}")

    (intent_dir / "config").mkdir(parents=True)
    (intent_dir / "config" / "actions.yaml").write_text(
        "actions:\n  - name: create_file\n    description: Creates a file."
    )
    # --- END OF FIX ---

    return tmp_path


def test_execute_goal_end_to_end(
    mock_cognitive_service, test_git_repo, monkeypatch, mocker
):
    """Tests the /execute_goal endpoint with a mocked cognitive service."""
    monkeypatch.chdir(test_git_repo)

    mocker.patch(
        "agents.development_cycle.ExecutionAgent.execute_plan",
    ).return_value = (True, "Plan executed successfully.")

    with TestClient(app) as client:
        response = client.post(
            "/execute_goal", json={"goal": "Create a hello world script"}
        )

        assert response.status_code == 200
        assert response.json()["status"] == "success"
