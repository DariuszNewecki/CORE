"""ADR-108 D4 — the stateless audit fails closed on governance collapse.

When the constitution declares rules but ZERO of them map to an enforceable
engine, the gate can evaluate nothing. Returning PASS there would be a
false-green (the BYOR root-split, or an empty / unreachable enforcement
mappings directory). The runner instead returns a distinct ``ERROR`` verdict
so the caller blocks on operator action — honoring the existing
``governance.no_governance_bypass`` rule ("if a precondition cannot be
evaluated, block").

The boundary matters: this fires only on TOTAL collapse. A partial
declared-only set (CORE's Class-A unmapped rules) and the all-skipped case
(rules mapped but every engine needs the graph / LLM) are honest coverage
gaps, not failures, and must stay non-blocking.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mind.governance.executable_rule import ExecutableRule
from mind.governance.stateless_audit import run_stateless_audit


def _rule(rule_id: str, engine: str) -> ExecutableRule:
    return ExecutableRule(rule_id=rule_id, engine=engine, params={}, enforcement="error")


@pytest.mark.asyncio
async def test_declared_but_zero_mapped_fails_closed(tmp_path: Path) -> None:
    """Rules declared + none mapped to an engine -> ERROR verdict, not PASS."""
    intent_repo = MagicMock()
    with (
        patch(
            "mind.governance.stateless_audit.extract_executable_rules",
            return_value=[],
        ),
        patch(
            "mind.governance.stateless_audit._count_declared_rules",
            return_value=4,
        ),
        patch(
            "mind.governance.stateless_audit.run_filtered_audit",
            new=AsyncMock(return_value=([], set(), {})),
        ) as mock_runner,
    ):
        result = await run_stateless_audit(intent_repo, tmp_path)

    assert result["verdict"] == "ERROR"
    assert result["passed"] is False
    assert result["stats"]["declared_rules"] == 4
    assert "governance collapse" in result["error"]
    # The gate must not even attempt a (vacuous) run — it short-circuits.
    mock_runner.assert_not_called()


@pytest.mark.asyncio
async def test_empty_constitution_does_not_fail_closed(tmp_path: Path) -> None:
    """No rules declared at all is legitimately nothing to enforce -> not ERROR."""
    intent_repo = MagicMock()
    with (
        patch(
            "mind.governance.stateless_audit.extract_executable_rules",
            return_value=[],
        ),
        patch(
            "mind.governance.stateless_audit._count_declared_rules",
            return_value=0,
        ),
        patch(
            "mind.governance.stateless_audit.run_filtered_audit",
            new=AsyncMock(return_value=([], set(), {})),
        ) as mock_runner,
    ):
        result = await run_stateless_audit(intent_repo, tmp_path)

    assert result["verdict"] != "ERROR"
    assert result["passed"] is True
    mock_runner.assert_called_once()


@pytest.mark.asyncio
async def test_mapped_rules_do_not_fail_closed(tmp_path: Path) -> None:
    """Declared rules that DO map to an engine run normally -> not ERROR."""
    intent_repo = MagicMock()
    with (
        patch(
            "mind.governance.stateless_audit.extract_executable_rules",
            return_value=[_rule("starter.no_bare_except", "regex_gate")],
        ),
        patch(
            "mind.governance.stateless_audit._count_declared_rules",
            return_value=4,
        ),
        patch(
            "mind.governance.stateless_audit.run_filtered_audit",
            new=AsyncMock(return_value=([], set(), {})),
        ) as mock_runner,
    ):
        result = await run_stateless_audit(intent_repo, tmp_path)

    assert result["verdict"] != "ERROR"
    mock_runner.assert_called_once()
    assert mock_runner.call_args.kwargs["rule_ids"] == ["starter.no_bare_except"]
