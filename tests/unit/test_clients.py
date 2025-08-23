# tests/unit/test_clients.py

from core.clients import BaseLLMClient


def test_base_llm_client_initialization():
    """Tests that the base LLM client initializes correctly."""
    client = BaseLLMClient(
        api_url="http://fake-api.com/v1",
        api_key="fake-key",
        model_name="fake-model",
    )
    assert client.model_name == "fake-model"
    assert "fake-key" in client.headers["Authorization"]
    assert client.api_url.endswith("/chat/completions")
