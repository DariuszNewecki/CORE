# tests/unit/test_clients.py
import pytest
import requests
from unittest.mock import MagicMock
from core.clients import OrchestratorClient

@pytest.fixture
def set_orchestrator_env(monkeypatch):
    monkeypatch.setenv("ORCHESTRATOR_API_URL", "http://fake-orchestrator.com/api/v1")
    monkeypatch.setenv("ORCHESTRATOR_API_KEY", "fake_orch_key")
    monkeypatch.setenv("ORCHESTRATOR_MODEL_NAME", "orch-model-v1")

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
    response_text = client.make_request(prompt_text, user_id="test_user")

    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args.kwargs
    
    sent_payload = call_kwargs["json"]
    assert sent_payload["model"] == "orch-model-v1"
    assert sent_payload["messages"] == [{"role": "user", "content": prompt_text}]