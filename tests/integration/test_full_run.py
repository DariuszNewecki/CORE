# tests/integration/test_full_run.py
"""
An end-to-end integration test for the CORE system.
This test simulates a real user request and verifies the entire
Plan -> Generate -> Execute cycle with the new agent architecture.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from core.main import app


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
    # FIX: Point the patch to where PlannerAgent is actually used.
    mocker.patch(
        "agents.development_cycle.PlannerAgent.create_execution_plan",
        return_value=mock_plan,
    )

    # FIX: Point the patch to where ExecutionAgent is actually used.
    mocker.patch(
        "agents.development_cycle.ExecutionAgent.execute_plan", new_callable=AsyncMock
    ).return_value = (True, "Plan executed successfully.")


@pytest.fixture
def test_git_repo(tmp_path: Path):
    """Creates a temporary, valid Git repository for the test to run in."""
    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    (tmp_path / "src").mkdir()
    # Create the constitutional files needed for the development cycle to run
    intent_dir = tmp_path / ".intent"
    (intent_dir / "policies").mkdir(parents=True)
    (intent_dir / "policies" / "agent_behavior_policy.yaml").write_text(
        """
planner_agent:
  max_retries: 1
  task_timeout: 30
execution_agent:
  auto_commit_on_success: false
  rollback_on_failure: false
"""
    )
    return tmp_path


def test_execute_goal_end_to_end(mock_agents, test_git_repo, monkeypatch, mocker):
    """Tests the entire /execute_goal endpoint flow with the refactored agents."""
    monkeypatch.chdir(test_git_repo)

    # FIX: Point all service mocks to where they are actually used.
    mocker.patch("agents.development_cycle.OrchestratorClient")
    mocker.patch("agents.development_cycle.GeneratorClient")
    mocker.patch("agents.development_cycle.GitService")
    # FIX: IntentGuard is no longer used in this path, so the mock is removed.

    with TestClient(app) as client:
        response = client.post(
            "/execute_goal", json={"goal": "Create a hello world script"}
        )

        assert response.status_code == 200
        assert response.json()["status"] == "success"
