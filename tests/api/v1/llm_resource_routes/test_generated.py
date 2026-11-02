from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from api.v1.llm_resource_routes import check_llm


# ID: d5443d85-621d-4891-bcdc-61608f64ecd7
async def test_check_llm():
    request = MagicMock()
    core_context = MagicMock()
    request.app.state.core_context = core_context

    session = MagicMock()

    fake_data = {"ok": True, "embed": "ok", "chat": "ok"}

    with (
        patch(
            "api.v1.llm_resource_routes.run_check_llm",
            new=AsyncMock(return_value=fake_data),
        ) as mock_run_check_llm,
        patch(
            "api.v1.llm_resource_routes.LlmResourceAuthoringResponse"
        ) as mock_response_cls,
    ):
        mock_response_cls.return_value = MagicMock()

        result = await check_llm(request=request, session=session)

    mock_run_check_llm.assert_awaited_once_with(core_context, session)
    mock_response_cls.assert_called_once_with(ok=True, data=fake_data, duration_sec=0.0)
    assert result is mock_response_cls.return_value


import pytest

from api.v1.llm_resource_routes import setup_llm


@pytest.mark.asyncio
# ID: 1237e7e7-e462-46d1-9f00-ebec0966d951
async def test_setup_llm():
    core_context = MagicMock()

    request = MagicMock()
    request.app.state.core_context = core_context

    payload = MagicMock()
    payload.write = True
    payload.api_url = "https://api.example.com"
    payload.embedding_model = "emb-model"
    payload.chat_model = "chat-model"
    payload.locality = "cloud"
    payload.embedding_api_url = "https://emb.example.com"
    payload.embedding_locality = "cloud"

    result = MagicMock()
    result.ok = True
    result.data = {"created": True}
    result.duration_sec = 0.5

    with patch(
        "api.v1.llm_resource_routes.run_setup_llm",
        new=AsyncMock(return_value=result),
    ) as mock_run_setup_llm:
        response = await setup_llm(request, payload)

    mock_run_setup_llm.assert_awaited_once_with(
        core_context,
        write=True,
        api_url="https://api.example.com",
        embedding_model="emb-model",
        chat_model="chat-model",
        locality="cloud",
        embedding_api_url="https://emb.example.com",
        embedding_locality="cloud",
    )
    assert response.ok is True
    assert response.data == {"created": True}
    assert response.duration_sec == 0.5


# ID: 5a2c7826-ecfb-4da3-8fed-cae7f5b59b70
def test_SetupLlmRequest():
    from api.v1.llm_resource_routes import SetupLlmRequest

    req = SetupLlmRequest(
        api_url="http://localhost:11434",
        embedding_model="nomic-embed-text",
        chat_model="llama3",
    )

    assert req.api_url == "http://localhost:11434"
    assert req.embedding_model == "nomic-embed-text"
    assert req.chat_model == "llama3"
    assert req.locality == "local"
    assert req.embedding_api_url == ""
    assert req.embedding_locality == ""
    assert req.write is False
