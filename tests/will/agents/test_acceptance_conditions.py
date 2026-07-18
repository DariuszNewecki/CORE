# tests/will/agents/test_acceptance_conditions.py
"""Tests for AcceptanceCondition implementations (ADR-135 D3, ADR-140 Amendment 2026-07-14)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.action_types import ActionResult
from will.agents.acceptance.conditions import (
    CompositeAcceptanceCondition,
    IntentGuardAcceptanceCondition,
    PytestAcceptanceCondition,
)


def _make_violation(rule_name: str = "code.tests.no_placeholder_test_body") -> MagicMock:
    v = MagicMock()
    v.rule_name = rule_name
    v.message = "No assertion"
    return v


@pytest.mark.asyncio
async def test_intent_guard_condition_accepts_valid_code(tmp_path) -> None:
    validation = MagicMock(is_valid=True, violations=[])
    intent_guard = MagicMock()
    intent_guard.validate_generated_code = MagicMock(return_value=validation)

    with patch(
        "body.governance.intent_guard.get_intent_guard", return_value=intent_guard
    ):
        cond = IntentGuardAcceptanceCondition(
            repo_root=tmp_path, target_path="tests/x/test_generated.py"
        )
        result = await cond.evaluate("def test_ok(): assert True")

    assert result.accepted
    assert result.violation_summary == ""


@pytest.mark.asyncio
async def test_intent_guard_condition_rejects_invalid_code(tmp_path) -> None:
    validation = MagicMock(is_valid=False, violations=[_make_violation()])
    intent_guard = MagicMock()
    intent_guard.validate_generated_code = MagicMock(return_value=validation)

    with patch(
        "body.governance.intent_guard.get_intent_guard", return_value=intent_guard
    ):
        cond = IntentGuardAcceptanceCondition(
            repo_root=tmp_path, target_path="tests/x/test_generated.py"
        )
        result = await cond.evaluate("def test_bad(): pass")

    assert not result.accepted
    assert "no_placeholder_test_body" in result.violation_summary
    assert result.violations


@pytest.mark.asyncio
async def test_pytest_condition_never_writes_target_path_only_delegates_candidate() -> None:
    """#815: PytestAcceptanceCondition must never write target_path itself — it
    passes the fully-assembled candidate to test.candidate_validate and lets that
    action own scratch materialization entirely."""
    executor = AsyncMock()
    executor.execute = AsyncMock(
        return_value=ActionResult(
            action_id="test.candidate_validate", ok=True, data={}
        )
    )

    cond = PytestAcceptanceCondition(
        executor=executor,
        source_file="src/x.py",
        target_path="tests/x/test_generated.py",
        base_content="from __future__ import annotations\n\n\ndef test_existing():\n    assert True\n",
    )

    result = await cond.evaluate("def test_new():\n    assert 1 == 1\n")

    assert result.accepted
    executor.execute.assert_called_once()
    call = executor.execute.call_args
    assert call.args == ("test.candidate_validate",)
    assert call.kwargs["write"] is False
    assert call.kwargs["source_file"] == "src/x.py"
    assert call.kwargs["target_path"] == "tests/x/test_generated.py"
    candidate_content = call.kwargs["candidate_content"]
    assert "def test_existing" in candidate_content
    assert "def test_new" in candidate_content


@pytest.mark.asyncio
async def test_pytest_condition_recomputes_not_accumulates_across_iterations() -> None:
    """A rejected candidate's body must not survive into the next iteration's
    candidate_content — each evaluate() call assembles base_content + this
    iteration's code only, never a prior iteration's rejected candidate."""
    executor = AsyncMock()
    executor.execute = AsyncMock(
        return_value=ActionResult(
            action_id="test.candidate_validate", ok=False, data={}
        )
    )

    cond = PytestAcceptanceCondition(
        executor=executor,
        source_file="src/x.py",
        target_path="tests/x/test_generated.py",
        base_content="",
    )

    await cond.evaluate("def test_attempt_one():\n    assert False\n")
    await cond.evaluate("def test_attempt_two():\n    assert True\n")

    assert executor.execute.call_count == 2
    second_content = executor.execute.call_args_list[1].kwargs["candidate_content"]
    assert "test_attempt_one" not in second_content
    assert "test_attempt_two" in second_content


@pytest.mark.asyncio
async def test_pytest_condition_rejects_on_sandbox_failure() -> None:
    executor = AsyncMock()
    executor.execute = AsyncMock(
        return_value=ActionResult(
            action_id="test.candidate_validate",
            ok=False,
            data={"error": "AssertionError: 1 != 2"},
        )
    )

    cond = PytestAcceptanceCondition(
        executor=executor,
        source_file="src/x.py",
        target_path="tests/x/test_generated.py",
        base_content="",
    )

    result = await cond.evaluate("def test_new():\n    assert 1 == 2\n")

    assert not result.accepted
    assert "AssertionError" in result.violation_summary


@pytest.mark.asyncio
async def test_pytest_condition_rejects_when_executor_not_wired() -> None:
    cond = PytestAcceptanceCondition(
        executor=object(),
        source_file="src/x.py",
        target_path="tests/x/test_generated.py",
        base_content="",
    )

    result = await cond.evaluate("def test_new(): assert True")

    assert not result.accepted
    assert "not wired" in result.violation_summary


@pytest.mark.asyncio
async def test_composite_short_circuits_on_first_failure() -> None:
    first = MagicMock()
    first.evaluate = AsyncMock(
        return_value=MagicMock(accepted=False, violation_summary="static violation")
    )
    second = MagicMock()
    second.evaluate = AsyncMock()

    composite = CompositeAcceptanceCondition([first, second])
    result = await composite.evaluate("code")

    assert not result.accepted
    assert result.violation_summary == "static violation"
    second.evaluate.assert_not_called()


@pytest.mark.asyncio
async def test_composite_accepts_only_when_all_conditions_pass() -> None:
    from will.agents.acceptance.conditions import AcceptanceResult

    first = MagicMock()
    first.evaluate = AsyncMock(return_value=AcceptanceResult(accepted=True, violation_summary=""))
    second = MagicMock()
    second.evaluate = AsyncMock(return_value=AcceptanceResult(accepted=True, violation_summary=""))

    composite = CompositeAcceptanceCondition([first, second])
    result = await composite.evaluate("code")

    assert result.accepted
    first.evaluate.assert_called_once_with("code")
    second.evaluate.assert_called_once_with("code")
