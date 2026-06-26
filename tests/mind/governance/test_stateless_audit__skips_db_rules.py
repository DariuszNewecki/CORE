"""F-10.1a — assert stateless audit partitions DB-dependent rules.

The stateless runner pre-filters rules whose engine requires the
knowledge graph (knowledge_gate) or the LLM provider + verdict cache
(llm_gate). The skipped rules surface in the result's `skipped_rules`
list with a structured reason so the CI gate's output is honest about
coverage rather than silently degraded.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mind.governance.executable_rule import ExecutableRule
from mind.governance.stateless_audit import (
    _STATELESS_SKIP_ENGINES,
    run_stateless_audit,
)


def _rule(rule_id: str, engine: str) -> ExecutableRule:
    """Minimal ExecutableRule for partition tests."""
    return ExecutableRule(
        rule_id=rule_id, engine=engine, params={}, enforcement="error"
    )


async def test_knowledge_gate_rules_are_skipped(tmp_path: Path) -> None:
    """knowledge_gate engines need the symbol graph; skipped in stateless mode."""
    rules = [
        _rule("graph.reachability", "knowledge_gate"),
        _rule("structure.imports", "ast_gate"),
    ]
    intent_repo = MagicMock()
    with (
        patch(
            "mind.governance.stateless_audit.extract_executable_rules",
            return_value=rules,
        ),
        patch(
            "mind.governance.stateless_audit.run_filtered_audit",
            new=AsyncMock(return_value=([], set(), {})),
        ) as mock_runner,
    ):
        result = await run_stateless_audit(intent_repo, tmp_path)

    skipped_ids = {entry["rule_id"] for entry in result["skipped_rules"]}
    assert "graph.reachability" in skipped_ids
    assert "structure.imports" not in skipped_ids
    mock_runner.assert_called_once()
    runnable_passed = mock_runner.call_args.kwargs["rule_ids"]
    assert runnable_passed == ["structure.imports"]


async def test_llm_gate_rules_are_skipped(tmp_path: Path) -> None:
    """llm_gate engines need network + cache; skipped in stateless mode.

    CI gates run on every PR; the latency + cost of live LLM invocation
    on every rule violates the F-10 user-facing promise of fast feedback.
    """
    rules = [
        _rule("prose.clarity", "llm_gate"),
        _rule("paths.glob", "glob_gate"),
    ]
    intent_repo = MagicMock()
    with (
        patch(
            "mind.governance.stateless_audit.extract_executable_rules",
            return_value=rules,
        ),
        patch(
            "mind.governance.stateless_audit.run_filtered_audit",
            new=AsyncMock(return_value=([], set(), {})),
        ),
    ):
        result = await run_stateless_audit(intent_repo, tmp_path)

    skipped_ids = {entry["rule_id"] for entry in result["skipped_rules"]}
    assert "prose.clarity" in skipped_ids
    assert "paths.glob" not in skipped_ids


async def test_skipped_entries_carry_structured_reason(tmp_path: Path) -> None:
    """Each skipped rule records engine + reason for CI-log honesty."""
    rules = [
        _rule("graph.a", "knowledge_gate"),
        _rule("prose.b", "llm_gate"),
    ]
    intent_repo = MagicMock()
    with (
        patch(
            "mind.governance.stateless_audit.extract_executable_rules",
            return_value=rules,
        ),
        patch(
            "mind.governance.stateless_audit.run_filtered_audit",
            new=AsyncMock(return_value=([], set(), {})),
        ),
    ):
        result = await run_stateless_audit(intent_repo, tmp_path)

    by_id = {entry["rule_id"]: entry for entry in result["skipped_rules"]}
    assert by_id["graph.a"]["engine"] == "knowledge_gate"
    assert "knowledge graph" in by_id["graph.a"]["reason"]
    assert by_id["prose.b"]["engine"] == "llm_gate"
    assert "LLM" in by_id["prose.b"]["reason"]


async def test_only_runnable_engines_pass_through(tmp_path: Path) -> None:
    """Non-DB engines (ast/regex/glob/cli/workflow) are forwarded to filtered_audit."""
    rules = [
        _rule("a", "ast_gate"),
        _rule("b", "regex_gate"),
        _rule("c", "glob_gate"),
        _rule("d", "cli_gate"),
        _rule("e", "workflow_gate"),
        _rule("skip1", "knowledge_gate"),
        _rule("skip2", "llm_gate"),
    ]
    intent_repo = MagicMock()
    with (
        patch(
            "mind.governance.stateless_audit.extract_executable_rules",
            return_value=rules,
        ),
        patch(
            "mind.governance.stateless_audit.run_filtered_audit",
            new=AsyncMock(return_value=([], set(), {})),
        ) as mock_runner,
    ):
        await run_stateless_audit(intent_repo, tmp_path)

    runnable_passed = mock_runner.call_args.kwargs["rule_ids"]
    assert set(runnable_passed) == {"a", "b", "c", "d", "e"}


def test_skip_engine_set_matches_design() -> None:
    """Constitutional guard: the skip set is exactly {knowledge_gate, llm_gate}.

    Adding a new engine to the skip list is an architectural decision
    that warrants an ADR addendum (per F-10.1a's "Option A" choice).
    This test fails loudly if the set drifts, forcing the change to
    surface in code review.
    """
    assert _STATELESS_SKIP_ENGINES == frozenset({"knowledge_gate", "llm_gate"})
