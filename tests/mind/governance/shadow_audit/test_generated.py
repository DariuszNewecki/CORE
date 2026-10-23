from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from mind.governance.shadow_audit import run_shadow_audit


# ID: d06884a1-05c2-4d36-a64e-e88389f1c2b1
def test_run_shadow_audit():
    intent_repo = MagicMock()
    repo_path = Path("/tmp/shadow_ws")

    runnable_rule = MagicMock()
    runnable_rule.rule_id = "rule-runnable"
    runnable_rule.engine = "static_gate"

    shadow_skip_rule = MagicMock()
    shadow_skip_rule.rule_id = "rule-shadow"
    shadow_skip_rule.engine = "llm_gate"

    stateless_skip_rule = MagicMock()
    stateless_skip_rule.rule_id = "rule-stateless"
    stateless_skip_rule.engine = "db_gate"

    finding_obj = MagicMock()
    finding_obj.as_dict = MagicMock(
        return_value={"rule_id": "rule-runnable", "severity": "low"}
    )

    mock_context = MagicMock()
    mock_context.policies = MagicMock()
    mock_context.enforcement_loader = MagicMock()
    mock_context.reload_governance = MagicMock()

    with (
        patch(
            "mind.governance.shadow_audit.AuditorContext",
            return_value=mock_context,
        ),
        patch(
            "mind.governance.shadow_audit.extract_executable_rules",
            return_value=[runnable_rule, shadow_skip_rule, stateless_skip_rule],
        ),
        patch(
            "mind.governance.shadow_audit._STATELESS_SKIP_ENGINES",
            frozenset({"db_gate"}),
        ),
        patch(
            "mind.governance.shadow_audit.run_filtered_audit",
            new=AsyncMock(
                return_value=([finding_obj], ["rule-runnable"], {"scanned": 1})
            ),
        ) as mock_run_filtered,
    ):
        result = asyncio.run(run_shadow_audit(intent_repo, repo_path, files=["a.py"]))

    mock_run_filtered.assert_awaited_once()
    call_args = mock_run_filtered.await_args
    assert call_args.args[0] is mock_context
    assert call_args.kwargs["rule_ids"] == ["rule-runnable"]
    assert call_args.kwargs["files"] == ["a.py"]

    assert result["mode"] == "shadow"
    assert result["verdict"] == "PASS"
    assert result["passed"] is True
    assert result["stats"]["total_rules"] == 3
    assert result["stats"]["runnable_rules"] == 1
    assert result["stats"]["skipped_rules_count"] == 2
    assert result["stats"]["scanned"] == 1
    assert result["findings"] == [{"rule_id": "rule-runnable", "severity": "low"}]
    assert result["executed_rule_ids"] == ["rule-runnable"]

    skipped_engines = {s["engine"] for s in result["skipped_rules"]}
    assert skipped_engines == {"llm_gate", "db_gate"}
