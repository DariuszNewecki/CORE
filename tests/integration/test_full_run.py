# tests/integration/test_full_run.py
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.mark.anyio
async def test_execute_goal_end_to_end(mock_core_env, mocker):
    from core.main import create_app
    from shared.config import settings

    mocker.patch(
        "core.agents.execution_agent.ExecutionAgent.execute_plan",
        new_callable=AsyncMock,
        return_value=(True, "Success"),
    )

    with patch.object(settings, "LLM_ENABLED", True):
        app = create_app()
        with TestClient(app) as client:
            response = client.post("/execute_goal", json={"goal": "test goal"})
            assert response.status_code == 200, response.text
            assert response.json()["status"] == "success"
