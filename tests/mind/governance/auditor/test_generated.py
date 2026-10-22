from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


# ID: 425dd6a9-6b0a-4949-a87e-4916dedd86e7
def test_ConstitutionalAuditor_run_full_audit_async():
    from mind.governance.auditor import AuditVerdict, ConstitutionalAuditor

    context = MagicMock()
    context.reload_governance = MagicMock()
    context.invalidate_file_cache = MagicMock()
    context.sweep_llm_gate_cache = AsyncMock()
    context.load_knowledge_graph = AsyncMock()
    context.intent_repo.root = MagicMock()

    auditor = ConstitutionalAuditor(context)

    law_state = MagicMock()
    law_state.relationship = "current"
    law_state.to_dict.return_value = {"relationship": "current"}

    with (
        patch(
            "mind.governance.auditor.observe_law_state", return_value=law_state
        ) as mock_observe,
        patch("mind.governance.auditor.EngineRegistry") as mock_registry,
        patch(
            "mind.governance.auditor.run_dynamic_rules", new=AsyncMock(return_value=[])
        ) as mock_run_rules,
        patch(
            "mind.governance.auditor.get_dynamic_execution_stats",
            return_value={"executed_dynamic_rules": 0},
        ) as mock_stats,
        patch(
            "mind.governance.auditor.law_drift_findings", return_value=[]
        ) as mock_drift,
    ):
        auditor._determine_verdict = MagicMock(return_value=AuditVerdict.PASS)

        result = asyncio.run(auditor.run_full_audit_async())

    context.reload_governance.assert_called_once()
    context.invalidate_file_cache.assert_called_once()
    context.sweep_llm_gate_cache.assert_awaited_once()
    context.load_knowledge_graph.assert_awaited_once()
    mock_observe.assert_called_once_with(context.intent_repo.root)
    mock_registry.initialize.assert_called_once_with(
        context.paths, llm_client=context.llm_client
    )
    mock_run_rules.assert_awaited_once()
    mock_stats.assert_called_once()

    assert result["findings"] == []
    assert result["verdict"] == AuditVerdict.PASS
    assert result["passed"] is True
    assert result["stats"]["law_state"] == {"relationship": "current"}
    assert result["law_state"] == {"relationship": "current"}
    assert isinstance(result["executed_rule_ids"], set)
    assert isinstance(result["crashed_rule_ids"], set)
    assert isinstance(result["unavailable_rule_ids"], set)


import pytest

from mind.governance.auditor import AuditVerdict, ConstitutionalAuditor


@pytest.mark.asyncio
# ID: fe48b7a8-f94b-4f2c-aa5d-e6310722ae5d
async def test_ConstitutionalAuditor():
    # Build a mocked AuditorContext with all attributes/methods the audit touches.
    context = MagicMock()
    context.reload_governance = MagicMock(return_value=None)
    context.invalidate_file_cache = MagicMock(return_value=None)
    context.sweep_llm_gate_cache = AsyncMock(return_value=None)
    context.load_knowledge_graph = AsyncMock(return_value=None)

    # intent_repo.root used by observe_law_state
    intent_repo = MagicMock()
    intent_repo.root = "/fake/intent/repo"
    context.intent_repo = intent_repo

    law_state = MagicMock()
    law_state.to_dict = MagicMock(return_value={"law": "of_record"})
    law_state.relationship = "of_record"

    auditor = ConstitutionalAuditor(context)

    # Patch module-level collaborators used inside run_full_audit_async.
    with (
        patch("mind.governance.auditor.observe_law_state", return_value=law_state),
        patch("mind.governance.auditor.EngineRegistry") as mock_engine_registry,
        patch(
            "mind.governance.auditor.run_dynamic_rules",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "mind.governance.auditor.get_dynamic_execution_stats",
            return_value={"executed_dynamic_rules": 0},
        ),
        patch(
            "mind.governance.auditor.law_drift_findings",
            return_value=[],
        ),
        patch.object(
            auditor, "_determine_verdict", return_value=AuditVerdict.PASS
        ) as mock_determine_verdict,
    ):
        result = await auditor.run_full_audit_async()

    # Assertions on the returned structured data
    assert result["findings"] == []
    assert "stats" in result
    assert result["executed_rule_ids"] == set()
    assert result["crashed_rule_ids"] == set()
    assert result["unavailable_rule_ids"] == set()
    assert result["verdict"] == AuditVerdict.PASS
    assert result["passed"] is True
    assert result["law_state"] == {"law": "of_record"}

    # Context lifecycle calls happened
    context.reload_governance.assert_called_once()
    context.invalidate_file_cache.assert_called_once()
    context.sweep_llm_gate_cache.assert_awaited_once()
    context.load_knowledge_graph.assert_awaited_once()

    # EngineRegistry initialized with context paths and llm client
    mock_engine_registry.initialize.assert_called_once_with(
        context.paths, llm_client=context.llm_client
    )

    # Verdict determination invoked
    mock_determine_verdict.assert_called_once()
