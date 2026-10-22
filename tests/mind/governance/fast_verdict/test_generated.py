from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from mind.governance.fast_verdict import run_fast_verdict


# ID: 2c2c5c7c-4212-4bdd-a6fc-b637318b51b0
async def test_run_fast_verdict(tmp_path: Path) -> None:
    target = tmp_path / "mod.py"
    target.write_text("print('hi')\n")

    intent_repo = MagicMock()

    fake_result = {
        "findings": [
            {
                "severity": "block",
                "check_id": "R1",
                "message": "bad",
                "path": "mod.py",
                "line": 1,
            },
            {
                "severity": "warning",
                "check_id": "R2",
                "message": "warn",
                "path": "mod.py",
                "line": 2,
            },
        ],
        "stats": {
            "skipped_context_level_ids": [],
            "failed_rule_ids": [],
        },
        "skipped_rules": [],
        "law_state": {"relationship": "ok", "drift_paths": []},
        "verdict": "FAIL",
        "executed_rule_ids": ["R1", "R2"],
    }

    with (
        patch(
            "mind.governance.fast_verdict.run_stateless_audit",
            new=AsyncMock(return_value=fake_result),
        ),
        patch(
            "mind.governance.fast_verdict._finding_summary",
            side_effect=lambda f: {
                "check_id": f.get("check_id"),
                "message": f.get("message"),
            },
        ),
        patch(
            "mind.governance.fast_verdict._not_evaluated",
            return_value=False,
        ),
        patch(
            "mind.governance.fast_verdict._with_enforcement",
            side_effect=lambda repo, rule_id: {
                "rule_id": rule_id,
                "enforcement": "warn",
            },
        ),
    ):
        result = await run_fast_verdict(intent_repo, tmp_path, files=["mod.py"])

    assert result["verdict"] == "BLOCKED"
    assert result["authoritative"] is False
    assert result["scope"]["files"] == ["mod.py"]
    assert result["scope"]["removed"] == []
    assert len(result["blocking"]) == 1
    assert result["blocking"][0]["check_id"] == "R1"
    assert len(result["other_findings"]) == 1
    assert result["other_findings"][0]["check_id"] == "R2"
    assert result["evaluated"] == ["R1", "R2"]
