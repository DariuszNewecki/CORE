from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
# ID: 80f8c532-3441-40b0-889c-a4c4c1408ed2
async def test_LLMMixin():
    from will.remediation.llm import LLMMixin

    mixin = LLMMixin.__new__(LLMMixin)
    mixin._target_rule = "RULE-123"
    mixin._ctx = MagicMock()

    client = MagicMock()
    mixin._ctx.cognitive_service.aget_client_for_role = AsyncMock(return_value=client)

    model = MagicMock()
    model.manifest = MagicMock(role="coder")
    model.invoke = AsyncMock(
        return_value=json.dumps({"code": "def foo():\n    return 42\n"})
    )

    with (
        patch("shared.ai.prompt_model.PromptModel.load", return_value=model),
        patch(
            "shared.ai.response_parser.extract_json",
            return_value={"code": "def foo():\n    return 42\n"},
        ),
    ):
        result = await mixin._invoke_llm(
            file_path="pkg/mod.py",
            source_code="def foo():\n    return 1\n",
            context_text="some context",
            violations_summary="violates RULE-123",
            architectural_context={"role": "utility", "strategies": ["rename"]},
        )

    assert result == "def foo():\n    return 42\n"
    model.invoke.assert_awaited_once()
    mixin._ctx.cognitive_service.aget_client_for_role.assert_awaited_once_with(
        model.manifest.role
    )
