from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from mind.logic.grc_applicability import GRCApplicabilityGate


# ID: 5a29bb7b-5e8c-43c4-ba34-4c1d9967ffef
def test_GRCApplicabilityGate_assess() -> None:
    import asyncio

    mock_llm = MagicMock()

    with patch("mind.logic.grc_applicability.PromptModel.load") as mock_load:
        mock_prompt_model = MagicMock()
        mock_prompt_model.invoke = AsyncMock(
            return_value=(
                '{"applicability": "in_scope", '
                '"detected_domains": ["finance", "risk"], '
                '"reasoning": "Framework applies to corpus"}'
            )
        )
        mock_load.return_value = mock_prompt_model

        gate = GRCApplicabilityGate(mock_llm)

        result = asyncio.run(
            gate.assess(
                framework_id="fw-123",
                framework_descriptor="SOX financial controls",
                corpus_excerpt="financial reporting corpus text",
            )
        )

    mock_prompt_model.invoke.assert_awaited_once_with(
        context={
            "framework": "SOX financial controls",
            "corpus_excerpt": "financial reporting corpus text",
        },
        client=mock_llm,
        user_id="grc_applicability_gate",
    )

    assert result.framework_id == "fw-123"
    assert result.applicability is not None
    assert result.detected_domains == ["finance", "risk"]
    assert result.rationale == "Framework applies to corpus"
