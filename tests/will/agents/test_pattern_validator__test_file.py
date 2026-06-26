"""Regression tests for #583: will-side PatternValidator must NOT short-circuit
``pattern_id="test_file"`` past the IntentGuard delegation.

Pre-#583, ``PatternValidator.validate_code`` short-circuited ``test_file`` to
syntax-only validation, bypassing the body-side
``PatternValidators.validate_test_file_pattern`` (the #574 import-resolution
gate) for the interactive code-gen path. These tests verify the delegation
path is now live for ``test_file``, while ``pure_function`` and
``stateless_utility`` continue to short-circuit (they have no per-pattern
validator on the body side).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from will.agents.code_generation.pattern_validator import PatternValidator


# ID: b274c858-8abb-4caf-911d-3dd8f401569e
async def test_test_file_delegates_to_intent_guard() -> None:
    """``pattern_id="test_file"`` must reach IntentGuard.validate_generated_code,
    not short-circuit on syntax alone. This is the #583 fix.
    """
    intent_guard = AsyncMock()
    intent_guard.validate_generated_code = AsyncMock(return_value=(True, []))

    validator = PatternValidator(intent_guard=intent_guard)
    await validator.validate_code(
        code="def test_x():\n    assert True\n",
        pattern_id="test_file",
        component_type="test",
        target_path="tests/test_generated.py",
    )

    intent_guard.validate_generated_code.assert_awaited_once()
    call_kwargs = intent_guard.validate_generated_code.await_args.kwargs
    assert call_kwargs["pattern_id"] == "test_file"
    assert call_kwargs["target_path"] == "tests/test_generated.py"


# ID: 5f00d4ea-4130-4e44-a302-8307adff971d
async def test_pure_function_still_short_circuits() -> None:
    """``pure_function`` has no per-pattern validator on the body side and
    correctly short-circuits to syntax-only. Confirms #583's fix is scoped
    to ``test_file`` and does not regress the other short-circuit cases.
    """
    intent_guard = AsyncMock()
    intent_guard.validate_generated_code = AsyncMock(return_value=(True, []))

    validator = PatternValidator(intent_guard=intent_guard)
    ok, violations = await validator.validate_code(
        code="def square(x):\n    return x * x\n",
        pattern_id="pure_function",
        component_type="logic",
        target_path="src/some/pure.py",
    )

    assert ok is True
    assert violations == []
    intent_guard.validate_generated_code.assert_not_awaited()


# ID: 01d8cb8e-fa26-4758-9fb5-283d31cd3223
async def test_stateless_utility_still_short_circuits() -> None:
    """``stateless_utility`` likewise short-circuits to syntax-only. Same scope
    discipline as ``pure_function`` — no per-pattern validator on body side.
    """
    intent_guard = AsyncMock()
    intent_guard.validate_generated_code = AsyncMock(return_value=(True, []))

    validator = PatternValidator(intent_guard=intent_guard)
    ok, violations = await validator.validate_code(
        code="def helper(x):\n    return len(x)\n",
        pattern_id="stateless_utility",
        component_type="logic",
        target_path="src/some/utility.py",
    )

    assert ok is True
    assert violations == []
    intent_guard.validate_generated_code.assert_not_awaited()


# ID: 76f32c4c-81c7-4adf-8785-e1ddb140d2ab
async def test_test_file_with_syntax_error_still_reaches_intent_guard() -> None:
    """A syntax error in ``test_file`` code must reach IntentGuard (which has
    its own syntax check in step 2 of validate_generated_code). The fix
    removed test_file from the will-side short-circuit; syntax checking is
    now IntentGuard's responsibility for this path, not the will side's.
    """
    intent_guard = AsyncMock()

    async def _capture(**kwargs: Any) -> tuple[bool, list]:
        return (False, [{"message": "syntax error from IntentGuard"}])

    intent_guard.validate_generated_code = AsyncMock(side_effect=_capture)

    validator = PatternValidator(intent_guard=intent_guard)
    await validator.validate_code(
        code="def broken(\n",  # unterminated paren
        pattern_id="test_file",
        component_type="test",
        target_path="tests/test_generated.py",
    )

    intent_guard.validate_generated_code.assert_awaited_once()


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
