"""#1374: run_check_llm calls each setup model once and says what is wrong."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from will.governance import llm_resource_runner as runner


def _context(vector=None, reply="OK", chat_error=None, vector_size=768):
    service = MagicMock()
    service.reload = AsyncMock()
    service.get_embedding_for_code = AsyncMock(return_value=vector)
    client = MagicMock()
    service.aget_client_for_role = AsyncMock(return_value=client)
    context = MagicMock()
    context.cognitive_service = service
    context.qdrant_service = MagicMock(vector_size=vector_size)
    model = MagicMock()
    model.manifest.role = "Coder"
    model.invoke = AsyncMock(side_effect=chat_error, return_value=reply)
    return context, model


async def _check(context, model):
    session = MagicMock()
    with patch("shared.models.prompt_model.PromptModel.load", return_value=model):
        result = await runner.run_check_llm(context, session)
    context.cognitive_service.reload.assert_awaited_once_with(session)
    return result


async def test_both_models_answering_is_ok() -> None:
    context, model = _context(vector=[0.0] * 768)
    result = await _check(context, model)
    assert result["ok"] is True
    assert result["embedding"]["dimensions"] == 768
    # the role comes from the prompt manifest, never a literal
    context.cognitive_service.aget_client_for_role.assert_awaited_once_with("Coder")


async def test_wrong_vector_size_names_both_sizes() -> None:
    context, model = _context(vector=[0.0] * 1536)
    result = await _check(context, model)
    assert result["ok"] is False
    assert "1536" in result["embedding"]["error"]
    assert "768" in result["embedding"]["error"]


async def test_a_failing_model_reports_its_error() -> None:
    context, model = _context(
        vector=[0.0] * 768, chat_error=RuntimeError("model not found")
    )
    result = await _check(context, model)
    assert result["ok"] is False
    assert result["embedding"]["ok"] is True
    assert result["chat"] == {"ok": False, "error": "RuntimeError: model not found"}


def test_the_check_prompt_loads_and_names_a_declared_role() -> None:
    from shared.infrastructure.intent.cognitive_roles import (
        load_cognitive_role_capabilities,
    )
    from shared.models.prompt_model import PromptModel

    model = PromptModel.load("llm_setup_check")
    assert model.manifest.role in load_cognitive_role_capabilities()
