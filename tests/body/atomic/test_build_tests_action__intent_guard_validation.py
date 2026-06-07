"""Regression tests for issue #210: build.tests IntentGuard validation
silently non-operational due to PatternValidators.validate AttributeError.

Two failure modes covered here:

Part A — PatternValidators dispatch (issue #210 root cause).
    Pre-fix, ``PatternValidators.validate(code, pattern_id, component_type)``
    did not exist. ``IntentGuard.validate_generated_code`` invoked it,
    raising AttributeError that was swallowed by a broad except in the
    build.tests step 6 wrapper. Generated code was effectively unvalidated.

Part B — fail-loud in build.tests step 5.
    Pre-fix, the try/except around the IntentGuard call logged any
    exception at WARNING and proceeded with the write. Genuine validator
    failures must now surface as ActionResult(ok=False), not warnings.
"""

from __future__ import annotations

from typing import Any

import pytest

from body.atomic.build_tests_action import _run_intent_guard_check
from body.governance.intent_pattern_validators import PatternValidators
from shared.models.constitutional_validation import ConstitutionalValidationResult


# ---- Part A: PatternValidators.validate dispatch -------------------------


# ID: ade13ae0-29d5-49c7-a11a-1a7b667bb082
def test_validate_test_file_with_no_imports_returns_no_violations() -> None:
    """``test_file`` validator only inspects import statements. Code with
    zero imports cannot violate either of the two import rules, so the
    dispatch returns an empty list.

    Pre-#574 this test asserted the deliberate-no-op behavior of pattern_id
    ``test_file``. Post-#574 the validator exists; this test confirms it
    still returns empty on an import-free input (regression coverage that
    we did not introduce false positives).
    """
    out = PatternValidators.validate(
        code="def test_x():\n    assert True\n",
        pattern_id="test_file",
        component_type="test",
        target_path="tests/test_x.py",
    )
    assert out == []


# ID: d9cb337f-1e50-45ab-bdce-716c6f1da845
def test_validate_unknown_pattern_id_returns_empty_list() -> None:
    """An unknown ``pattern_id`` falls through to the deliberate "no validator
    applies" empty-list branch — not an exception, not a fabricated violation.

    Pre-deletion this test asserted that ``"inspect"`` dispatched to a
    legacy hardcoded validator. The legacy inspect/action/check/run
    validators were dead code (zero production callers) and were removed;
    this test now exercises the fallthrough branch with a synthetic unknown
    pattern_id to keep regression coverage on the dispatch infrastructure.
    """
    out = PatternValidators.validate(
        code="def cmd():\n    pass\n",
        pattern_id="not_a_registered_pattern",
        component_type="cli",
        target_path="src/cli/cmd.py",
    )
    assert out == []


# ---- Part B: build.tests fail-loud helper --------------------------------


class _FakeIntentGuardRaises:
    """Stand-in IntentGuard whose validate_generated_code always raises."""

    def validate_generated_code(self, **_: Any) -> ConstitutionalValidationResult:
        raise RuntimeError("synthetic validator failure")


class _FakeIntentGuardInvalid:
    """Stand-in IntentGuard that returns a result with violations."""

    def validate_generated_code(self, **_: Any) -> ConstitutionalValidationResult:
        result = ConstitutionalValidationResult(is_valid=True, source="fake")
        violation = type(
            "V",
            (),
            {
                "rule_name": "synthetic_violation",
                "message": "intentional",
                "severity": "error",
                "path": "tests/foo.py",
            },
        )()
        result.add_violation(violation)
        return result


class _FakeIntentGuardClean:
    """Stand-in IntentGuard that returns is_valid=True with no violations."""

    def validate_generated_code(self, **_: Any) -> ConstitutionalValidationResult:
        return ConstitutionalValidationResult(is_valid=True, source="fake")


# ID: 36030e8f-f8ae-423d-8090-850eeeb569d9
def test_intent_guard_exception_returns_action_result_failure() -> None:
    """A validator that raises must NOT be silently swallowed; the helper
    returns ActionResult(ok=False) so build.tests stops and the proposal
    is marked failed.
    """
    result = _run_intent_guard_check(
        _FakeIntentGuardRaises(),  # type: ignore[arg-type]
        generated_code="def test_x():\n    pass\n",
        test_file="tests/test_x.py",
        start=0.0,
    )
    assert result is not None, "validator exception must be surfaced, not swallowed"
    assert result.ok is False
    assert "IntentGuard validation failed" in result.data["error"]
    assert result.data["test_file"] == "tests/test_x.py"


# ID: 12897f05-6352-4370-b0db-7048e1246d85
def test_intent_guard_violations_return_action_result_failure() -> None:
    """is_valid=False with violations must yield ok=False and a structured
    violations payload — not a WARNING-and-proceed.
    """
    result = _run_intent_guard_check(
        _FakeIntentGuardInvalid(),  # type: ignore[arg-type]
        generated_code="def test_x():\n    pass\n",
        test_file="tests/test_x.py",
        start=0.0,
    )
    assert result is not None
    assert result.ok is False
    assert result.data["error"] == "intent_guard_violations"
    violations = result.data["violations"]
    assert len(violations) == 1
    assert violations[0]["rule_name"] == "synthetic_violation"
    assert violations[0]["severity"] == "error"


# ID: e8d49f57-ad93-4bad-b6a4-6c8e3cf70c17
def test_intent_guard_clean_pass_returns_none() -> None:
    """When validation passes, the helper returns None so the caller
    proceeds to the file write step.
    """
    result = _run_intent_guard_check(
        _FakeIntentGuardClean(),  # type: ignore[arg-type]
        generated_code="def test_x():\n    pass\n",
        test_file="tests/test_x.py",
        start=0.0,
    )
    assert result is None


# ---- Part C: end-to-end through real PatternValidators (issue #574) ------


class _FakeIntentGuardWithRealPatternValidator:
    """Stand-in IntentGuard that runs the real ``PatternValidators`` dispatch
    for the supplied pattern_id. Lets us verify the build.tests helper
    integrates with the new ``test_file`` validator end-to-end without
    instantiating a full IntentGuard (which is heavy — loads all of
    ``.intent/``).

    The real validator's import-resolution logic runs against the live
    Python path inside the test process — that is the property we want to
    exercise (a hallucinated module would not resolve here either).
    """

    def validate_generated_code(
        self,
        *,
        code: str,
        pattern_id: str,
        component_type: str,
        target_path: str,
        **_: Any,
    ) -> ConstitutionalValidationResult:
        result = ConstitutionalValidationResult(is_valid=True, source="fake-real")
        for v in PatternValidators.validate(
            code, pattern_id, component_type, target_path
        ):
            result.add_violation(v)
        return result


# ID: cb681293-e3b7-42ba-90a3-bec5c993d026
def test_hallucinated_imports_through_real_validator_returns_failure() -> None:
    """End-to-end with the real ``PatternValidators.validate_test_file_pattern``:
    a hallucinated module in generated test code surfaces as
    ``ActionResult(ok=False)`` with the rule_name preserved through the
    helper's violations payload. Closes #574.
    """
    result = _run_intent_guard_check(
        _FakeIntentGuardWithRealPatternValidator(),  # type: ignore[arg-type]
        generated_code="from shared.domain.engine import EngineResult\n",
        test_file="tests/test_generated.py",
        start=0.0,
    )
    assert result is not None, "hallucinated import must be surfaced"
    assert result.ok is False
    assert result.data["error"] == "intent_guard_violations"
    violations = result.data["violations"]
    assert len(violations) == 1
    assert violations[0]["rule_name"] == "code.imports.generated_must_resolve"
    assert violations[0]["severity"] == "error"


# ID: 05948855-aeaa-4eaa-aed2-376fa2afc6e7
def test_clean_imports_through_real_validator_returns_none() -> None:
    """End-to-end with the real validator: a code sample whose every import
    resolves cleanly produces no violations and the helper returns None
    so build.tests proceeds to write.
    """
    result = _run_intent_guard_check(
        _FakeIntentGuardWithRealPatternValidator(),  # type: ignore[arg-type]
        generated_code=(
            "from __future__ import annotations\n"
            "import pytest\n"
            "from shared.path_resolver import PathResolver\n"
            "def test_x():\n    assert True\n"
        ),
        test_file="tests/test_generated.py",
        start=0.0,
    )
    assert result is None


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
