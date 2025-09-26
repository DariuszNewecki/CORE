# tests/integration/test_full_run.py
"""
An end-to-end integration test for the CORE system.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml
from fastapi.testclient import TestClient

from core.main import app
from shared import config


@pytest.fixture
def mock_cognitive_service(mocker):
    """Mocks the CognitiveService to return mock clients with async methods."""
    mock_service = MagicMock()
    planner_client = MagicMock()
    planner_client.make_request.return_value = json.dumps(
        [
            {
                "step": "Create a simple Python file.",
                "action": "create_file",
                "params": {"file_path": "src/hello.py", "code": "print('hello')"},
            }
        ]
    )
    execution_client = MagicMock()
    execution_client.make_request_async = AsyncMock(return_value="print('hello world')")

    def get_client_side_effect(role_name, task_context=None):
        return planner_client if role_name == "Planner" else execution_client

    mock_service.get_client_for_role.side_effect = get_client_side_effect

    mocker.patch("core.main.CognitiveService", return_value=mock_service)
    return mock_service


@pytest.fixture
def test_git_repo(tmp_path: Path, monkeypatch, mocker):
    """
    Creates a temporary, valid Git repository with a complete and valid
    mock constitution for integration testing.
    """
    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)

    monkeypatch.setenv("REPO_PATH", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path}/test.db")

    intent_dir = tmp_path / ".intent"
    charter_dir = intent_dir / "charter"
    mind_dir = intent_dir / "mind"

    (charter_dir / "policies").mkdir(parents=True, exist_ok=True)
    (mind_dir / "knowledge").mkdir(parents=True, exist_ok=True)
    (mind_dir / "prompts").mkdir(parents=True, exist_ok=True)
    (mind_dir / "config").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src").mkdir(exist_ok=True)
    (tmp_path / "reports").mkdir(exist_ok=True)

    # Minimal charter policies
    (charter_dir / "policies" / "agent_policy.yaml").write_text(
        yaml.dump({"rules": []})
    )
    (charter_dir / "policies" / "safety_policy.yaml").write_text(
        yaml.dump({"rules": []})
    )
    (charter_dir / "policies" / "agent_behavior_policy.yaml").write_text(
        yaml.dump({"execution_agent": {"max_correction_attempts": 1}})
    )

    # Minimal mind knowledge
    (mind_dir / "knowledge" / "source_structure.yaml").write_text(
        yaml.dump({"structure": []})
    )
    (mind_dir / "knowledge" / "cognitive_roles.yaml").write_text(
        yaml.dump({"cognitive_roles": []})
    )
    (mind_dir / "knowledge" / "resource_manifest.yaml").write_text(
        yaml.dump({"llm_resources": []})
    )

    (mind_dir / "prompts" / "planner_agent.prompt").write_text("Goal: {goal}")

    (mind_dir / "config" / "actions.yaml").write_text(
        yaml.dump(
            {
                "actions": [
                    {
                        "name": "create_file",
                        "description": "Creates a file.",
                        "required_parameters": ["file_path", "code"],
                    }
                ]
            }
        )
    )

    meta_content = {
        "charter": {
            "policies": {
                "agent_policy": "charter/policies/agent_policy.yaml",
                "safety_policy": "charter/policies/safety_policy.yaml",
            }
        }
    }
    (intent_dir / "meta.yaml").write_text(yaml.dump(meta_content))

    # Mock the async graph loading to prevent real DB calls in this test
    mocker.patch(
        "core.knowledge_service.KnowledgeService._get_graph_from_db",
        new_callable=AsyncMock,
        return_value={"symbols": {}},
    )

    monkeypatch.setattr(config.settings, "MIND", intent_dir)

    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_execute_goal_end_to_end(mock_cognitive_service, test_git_repo, mocker):
    """Tests the /execute_goal endpoint with a mocked cognitive service."""

    mocker.patch(
        "core.agents.plan_executor.PlanExecutor.execute_plan",
        new_callable=AsyncMock,
        return_value=(True, "Plan executed successfully."),
    )

    # --- THIS IS THE FIX ---
    # We now run the TestClient inside the app's lifespan context
    with TestClient(app) as client:
        response = client.post(
            "/execute_goal", json={"goal": "Create a hello world script"}
        )

        assert response.status_code == 200
        assert response.json()["status"] == "success"
    # --- END OF FIX ---
