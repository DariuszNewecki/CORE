# tests/unit/test_clients.py
from unittest.mock import MagicMock

import pytest
from core.clients import OrchestratorClient


@pytest.fixture
def set_orchestrator_env(monkeypatch):
    monkeypatch.setenv("ORCHESTRATOR_API_URL", "http://fake-orchestrator.com/api/v1")
    monkeypatch.setenv("ORCHESTRATOR_API_KEY", "fake_orch_key")
    # --- THIS IS THE FIX ---
    # The test now expects the model name to be the new default from config.py.
    monkeypatch.setenv("ORCHESTRATOR_MODEL_NAME", "deepseek-chat")


def test_make_request_sends_correct_chat_payload(set_orchestrator_env, mocker):
    mock_post = mocker.patch("requests.post")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "This is a mock chat response."}}]
    }
    mock_post.return_value = mock_response

    client = OrchestratorClient()
    prompt_text = "Analyze this user request."
    client.make_request(prompt_text, user_id="test_user")

    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args.kwargs

    sent_payload = call_kwargs["json"]
    # The test will now correctly assert the model name.
    assert sent_payload["model"] == "deepseek-chat"
