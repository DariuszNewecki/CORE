from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mind.governance.filtered_audit import run_filtered_audit


@pytest.mark.asyncio
# ID: 7ee00dd2-36e7-4542-9fbc-6b66522fae1b
async def test_run_filtered_audit():
    context = MagicMock()
    context.policies = ["policy-a"]
    context.enforcement_loader = MagicMock()
    context.repo_path = "/repo"
    context.reload_governance = MagicMock()
    context.invalidate_file_cache = MagicMock()
    context.sweep_llm_gate_cache = AsyncMock()

    rule = MagicMock()
    rule.rule_id = "rule-1"
    rule.is_context_level = False
    rule.enforcement = "advisory"

    finding = MagicMock()
    finding.as_dict = MagicMock(return_value={"check_id": "c1"})

    with (
        patch(
            "mind.governance.rule_extractor.extract_executable_rules",
            return_value=[rule],
        ),
        patch(
            "mind.governance.rule_executor.execute_rule",
            new=AsyncMock(return_value=[finding]),
        ),
        patch(
            "mind.governance.filtered_audit.normalize_file_filter",
            return_value=None,
        ),
        patch("mind.governance.filtered_audit.RuleFilter") as mock_rule_filter_cls,
    ):
        mock_rule_filter = MagicMock()
        mock_rule_filter.matches = MagicMock(return_value=True)
        mock_rule_filter_cls.return_value = mock_rule_filter

        findings, executed, stats = await run_filtered_audit(
            context, rule_ids=["rule-1"]
        )

    assert findings == [{"check_id": "c1"}]
    assert executed == {"rule-1"}
    assert stats["total_rules"] == 1
    assert stats["filtered_rules"] == 1
    assert stats["executed_rules"] == 1
    assert stats["total_findings"] == 1
    context.reload_governance.assert_called_once()
    context.invalidate_file_cache.assert_called_once()
    context.sweep_llm_gate_cache.assert_awaited_once()
