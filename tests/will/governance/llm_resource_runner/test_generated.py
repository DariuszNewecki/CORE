from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from will.governance.llm_resource_runner import run_author_llm_resource


@pytest.mark.asyncio
# ID: ee0adac1-9be4-450a-8d9d-9f2b7334e9f4
async def test_run_author_llm_resource():
    context = MagicMock()
    definition = {"name": "example", "foo": "bar"}
    expected = MagicMock()

    mock_executor_instance = MagicMock()
    mock_executor_instance.execute = AsyncMock(return_value=expected)

    with patch(
        "body.atomic.executor.ActionExecutor",
        return_value=mock_executor_instance,
    ) as mock_executor_cls:
        result = await run_author_llm_resource(context, True, definition)

    mock_executor_cls.assert_called_once_with(context)
    mock_executor_instance.execute.assert_awaited_once_with(
        "author.llm_resource", write=True, definition=definition
    )
    assert result is expected


from will.governance.llm_resource_runner import run_check_llm


# ID: 472acfea-a9d5-4eee-a758-60770b5d30eb
async def test_run_check_llm():
    from shared.models.prompt_model import PromptModel

    context = MagicMock()
    service = MagicMock()
    service.reload = AsyncMock(return_value=None)
    service.get_embedding_for_code = AsyncMock(return_value=[0.1, 0.2, 0.3])
    service.aget_client_for_role = AsyncMock(return_value=MagicMock())
    context.cognitive_service = service

    qdrant = MagicMock()
    qdrant.vector_size = 3
    context.qdrant_service = qdrant

    session = MagicMock()

    fake_model = MagicMock()
    fake_model.manifest.role = "chat"
    fake_model.invoke = AsyncMock(return_value="hello there")

    with patch.object(PromptModel, "load", return_value=fake_model) as mock_load:
        result = await run_check_llm(context, session)

    mock_load.assert_called_once_with("llm_setup_check")
    service.reload.assert_awaited_once_with(session)
    service.get_embedding_for_code.assert_awaited_once()

    assert result["embedding"]["ok"] is True
    assert result["embedding"]["dimensions"] == 3
    assert result["embedding"]["expected_dimensions"] == 3
    assert result["chat"]["ok"] is True
    assert result["chat"]["reply"] == "hello there"
    assert result["ok"] is True



from will.governance.llm_resource_runner import run_setup_llm


# ID: 33971a5e-97f8-497c-a795-8dec2aba5e61
async def test_run_setup_llm():
    context = MagicMock()
    expected_result = MagicMock()

    mock_executor_instance = MagicMock()
    mock_executor_instance.execute = AsyncMock(return_value=expected_result)

    with patch(
        "body.atomic.executor.ActionExecutor",
        return_value=mock_executor_instance,
    ) as mock_executor_cls:
        result = await run_setup_llm(
            context=context,
            write=True,
            api_url="https://api.example.com",
            embedding_model="embed-model",
            chat_model="chat-model",
            locality="local",
            embedding_api_url="https://embed.example.com",
            embedding_locality="remote",
        )

    mock_executor_cls.assert_called_once_with(context)
    mock_executor_instance.execute.assert_awaited_once_with(
        "setup.llm",
        write=True,
        api_url="https://api.example.com",
        embedding_model="embed-model",
        chat_model="chat-model",
        locality="local",
        embedding_api_url="https://embed.example.com",
        embedding_locality="remote",
    )
    assert result is expected_result
