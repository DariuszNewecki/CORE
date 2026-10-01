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


from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
# ID: 72ef4912-ca13-4d18-9aa4-f01a24d1eb6e
async def test_KnowledgeGateEngine() -> None:
    engine = KnowledgeGateEngine()

    # supported_check_types returns the declared set of check types.
    assert "table_has_records" in engine.supported_check_types()
    assert "capability_assignment" in engine.supported_check_types()

    # verify() without AuditorContext returns a failure EngineResult.
    result = engine.verify("some/file.py", {})
    assert result.ok is False
    assert result.engine_id == "knowledge_gate"

    # verify_context with no check_type yields no findings.
    context = MagicMock()
    assert await engine.verify_context(context, {}) == []

    # verify_context dispatches table_has_records; missing table -> no findings.
    assert (
        await engine.verify_context(context, {"check_type": "table_has_records"}) == []
    )

    # table_has_records happy path: whitelisted table with a row present.
    db_session = MagicMock()
    exec_result = MagicMock()
    exec_result.scalar.return_value = True
    db_session.execute = AsyncMock(return_value=exec_result)
    context.db_session = db_session

    findings = await engine._check_table_has_records(
        context, {"table": "core.symbol_vector_links"}
    )
    assert findings == []
    db_session.execute.assert_awaited_once()
