"""#961 -- a scoped offline audit cannot say PASS while a blocking
context-level rule went unevaluated.

`core-admin code audit --offline --files <f>` skips every context-level
rule. Before the fix the verdict ignored that, so in a project with no
service-dependent skips a scoped audit said PASS while every cross-file
rule, blocking ones included, never ran. The skip is now handled like the
#907 service skips: listed in skipped_rules with its enforcement level,
and a blocking one makes the verdict DEGRADED (never PASS, never FAIL).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from mind.governance.executable_rule import ExecutableRule
from mind.governance.stateless_audit import run_stateless_audit
from shared.infrastructure.intent.law_state import LawState


_LAW_MATCH = LawState(relationship="MATCH", head_sha="0" * 40)


def _rule(rule_id: str, engine: str, enforcement: str) -> ExecutableRule:
    return ExecutableRule(
        rule_id=rule_id, engine=engine, params={}, enforcement=enforcement
    )


async def _run(rules: list[ExecutableRule], skipped_ctx: list[str], tmp_path: Path):
    stats = {"skipped_context_level_ids": skipped_ctx}
    executed = {r.rule_id for r in rules} - set(skipped_ctx)
    with (
        patch(
            "mind.governance.stateless_audit.observe_law_state",
            return_value=_LAW_MATCH,
        ),
        patch(
            "mind.governance.stateless_audit.extract_executable_rules",
            return_value=rules,
        ),
        patch(
            "mind.governance.stateless_audit._count_declared_rules",
            return_value=len(rules),
        ),
        patch(
            "mind.governance.stateless_audit.run_filtered_audit",
            new=AsyncMock(return_value=([], executed, stats)),
        ),
    ):
        return await run_stateless_audit(MagicMock(), tmp_path, files=["src/a.py"])


async def test_skipped_blocking_context_level_rule_is_degraded(tmp_path: Path) -> None:
    rules = [
        _rule("per.file", "ast_gate", "blocking"),
        _rule("cross.file", "workflow_gate", "blocking"),
    ]
    result = await _run(rules, ["cross.file"], tmp_path)
    assert result["verdict"] == "DEGRADED"
    assert result["passed"] is False
    assert result["stats"]["skipped_blocking_rule_ids"] == ["cross.file"]
    entry = next(e for e in result["skipped_rules"] if e["rule_id"] == "cross.file")
    assert entry["enforcement"] == "blocking"
    assert entry["engine"] == "workflow_gate"
    assert "--files" in entry["reason"]
    assert "cross.file" not in result["executed_rule_ids"]


async def test_skipped_reporting_context_level_rule_is_listed_but_passes(
    tmp_path: Path,
) -> None:
    rules = [
        _rule("per.file", "ast_gate", "blocking"),
        _rule("cross.file", "workflow_gate", "reporting"),
    ]
    result = await _run(rules, ["cross.file"], tmp_path)
    assert result["verdict"] == "PASS"
    assert [e["rule_id"] for e in result["skipped_rules"]] == ["cross.file"]
    assert result["stats"]["skipped_blocking_rule_ids"] == []
