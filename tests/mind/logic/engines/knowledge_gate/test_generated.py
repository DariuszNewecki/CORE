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




# ID: 040da51c-d832-48f8-b9cc-958c52662347
def test_KnowledgeGateEngine_supported_check_types() -> None:
    result = KnowledgeGateEngine.supported_check_types()

    assert isinstance(result, set)
    assert result == {
        "capability_assignment",
        "ast_duplication",
        "semantic_duplication",
        "table_has_records",
        "orphan_file_check",
        "capability_taxonomy_whitelist",
    }
