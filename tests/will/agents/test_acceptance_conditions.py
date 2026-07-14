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
async def test_pytest_condition_writes_full_content_then_validates() -> None:
    executor = AsyncMock()
    executor.execute = AsyncMock(
        return_value=ActionResult(action_id="test.sandbox_validate", ok=True, data={})
    )
    file_service = MagicMock()
    file_service.write = MagicMock()

    cond = PytestAcceptanceCondition(
        executor=executor,
        source_file="src/x.py",
        target_path="tests/x/test_generated.py",
        base_content="from __future__ import annotations\n\n\ndef test_existing():\n    assert True\n",
        file_service=file_service,
    )

    result = await cond.evaluate("def test_new():\n    assert 1 == 1\n")

    assert result.accepted
    written_path, written_content = file_service.write.call_args[0]
    assert written_path == "tests/x/test_generated.py"
    assert "def test_existing" in written_content
    assert "def test_new" in written_content
    executor.execute.assert_called_once_with(
        "test.sandbox_validate", write=False, source_file="src/x.py"
    )


@pytest.mark.asyncio
async def test_pytest_condition_overwrites_not_appends_across_iterations() -> None:
    """A rejected candidate's body must not survive into the next iteration's write."""
    executor = AsyncMock()
    executor.execute = AsyncMock(
        return_value=ActionResult(action_id="test.sandbox_validate", ok=False, data={})
    )
    file_service = MagicMock()

    cond = PytestAcceptanceCondition(
        executor=executor,
        source_file="src/x.py",
        target_path="tests/x/test_generated.py",
        base_content="",
        file_service=file_service,
    )

    await cond.evaluate("def test_attempt_one():\n    assert False\n")
    await cond.evaluate("def test_attempt_two():\n    assert True\n")

    assert file_service.write.call_count == 2
    second_content = file_service.write.call_args_list[1][0][1]
    assert "test_attempt_one" not in second_content
    assert "test_attempt_two" in second_content


@pytest.mark.asyncio
async def test_pytest_condition_rejects_on_sandbox_failure() -> None:
    executor = AsyncMock()
    executor.execute = AsyncMock(
        return_value=ActionResult(
            action_id="test.sandbox_validate",
            ok=False,
            data={"error": "AssertionError: 1 != 2"},
        )
    )
    file_service = MagicMock()

    cond = PytestAcceptanceCondition(
        executor=executor,
        source_file="src/x.py",
        target_path="tests/x/test_generated.py",
        base_content="",
        file_service=file_service,
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
        file_service=MagicMock(),
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
