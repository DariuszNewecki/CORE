from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from mind.governance.stateless_audit import run_stateless_audit


# ID: 09006e8b-a461-44fd-8c39-5aada6de803d
def test_run_stateless_audit(tmp_path: Path) -> None:
    intent_repo = MagicMock()
    intent_repo.root = tmp_path

    rule = MagicMock()
    rule.rule_id = "core.rule_one"
    rule.engine = "python_gate"
    rule.enforcement = "blocking"

    context = MagicMock()
    context.policies = MagicMock()
    context.enforcement_loader = MagicMock()

    law_state = MagicMock()
    law_state.relationship = "law_of_record"
    law_state.to_dict.return_value = {"relationship": "law_of_record"}

    finding = MagicMock()
    finding.as_dict.return_value = {
        "rule_id": "core.rule_one",
        "severity": "low",
        "context": {"finding_type": "SOMETHING"},
    }

    stats_dict = {"skipped_context_level_ids": []}

    verdict_policy = {
        "ignored_finding_types": ["ENFORCEMENT_FAILURE", "ENFORCEMENT_UNAVAILABLE"],
        "degraded_on": ["any_blocking_unavailable_rules"],
    }

    with (
        patch(
            "mind.governance.stateless_audit.AuditorContext",
            return_value=context,
        ),
        patch(
            "mind.governance.stateless_audit.observe_law_state",
            return_value=law_state,
        ),
        patch(
            "mind.governance.stateless_audit.extract_executable_rules",
            return_value=[rule],
        ),
        patch(
            "mind.governance.stateless_audit._count_declared_rules",
            return_value=1,
        ),
        patch(
            "mind.governance.stateless_audit.run_filtered_audit",
            new=AsyncMock(return_value=([finding], ["core.rule_one"], stats_dict)),
        ),
        patch(
            "mind.governance.stateless_audit.law_drift_findings",
            return_value=[],
        ),
        patch(
            "mind.governance.stateless_audit.load_audit_verdict_policy",
            return_value=verdict_policy,
        ),
        patch(
            "mind.governance.stateless_audit.law_drift_degrades",
            return_value=False,
        ),
    ):
        result = asyncio.run(run_stateless_audit(intent_repo, tmp_path))

    context.reload_governance.assert_called_once()
    assert result["verdict"] == "PASS"
    assert result["passed"] is True
    assert result["mode"] == "stateless"
    assert result["run_id"] is None
    assert result["executed_rule_ids"] == ["core.rule_one"]
    assert result["stats"]["total_rules"] == 1
    assert result["stats"]["runnable_rules"] == 1
    assert result["stats"]["skipped_blocking_rules_count"] == 0
