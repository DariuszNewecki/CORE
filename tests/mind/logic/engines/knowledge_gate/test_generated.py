from __future__ import annotations

from unittest.mock import MagicMock, patch

from mind.logic.engines.knowledge_gate import KnowledgeGateEngine


# ID: 98461e9a-a0a3-41cd-a5a6-f6c10b3bc64b
async def test_KnowledgeGateEngine_verify_context():
    engine = KnowledgeGateEngine()
    context = MagicMock()

    with patch.object(
        engine, "_check_capability_assignment", return_value=["finding"]
    ) as mock_check:
        result = await engine.verify_context(
            context, {"check_type": "capability_assignment"}
        )

    assert result == ["finding"]
    mock_check.assert_called_once_with(context, {"check_type": "capability_assignment"})
