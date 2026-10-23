from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from mind.coherence.llm_judge import judge_contradiction_pair


# ID: 5842632a-882d-4bdb-af23-9976d364e166
async def test_judge_contradiction_pair():
    cognitive_service = MagicMock()
    cognitive_service.aget_client_for_role = AsyncMock(return_value=MagicMock())

    model = MagicMock()
    model.manifest = MagicMock(role="analyst")
    model.invoke = AsyncMock(
        return_value=(
            '[{"claim": "DOC A mandates X while DOC B forbids X", '
            '"rationale": "The two claims conflict on the allowed behavior."}]'
        )
    )

    with (
        patch(
            "shared.ai.prompt_model.PromptModel.load",
            return_value=model,
        ),
        patch(
            "mind.coherence.llm_judge.extract_json_safe",
            return_value=[
                {
                    "claim": "DOC A mandates X while DOC B forbids X",
                    "rationale": "The two claims conflict on the allowed behavior.",
                }
            ],
        ),
    ):
        result = await judge_contradiction_pair(
            cognitive_service=cognitive_service,
            text_a="System X must always be enabled.",
            source_a="adr-001.md",
            text_b="System X must never be enabled.",
            source_b="adr-002.md",
            tier="high",
        )

    assert result is not None
    assert result.claim == "DOC A mandates X while DOC B forbids X"
    assert result.rationale == "The two claims conflict on the allowed behavior."
    cognitive_service.aget_client_for_role.assert_awaited_once()
