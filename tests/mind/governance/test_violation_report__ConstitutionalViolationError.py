"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/mind/governance/violation_report.py
- Symbol: ConstitutionalViolationError
- Generated: 2026-01-11 01:45:54
- 2026-06-07 (#572 Cat B batch 14): ConstitutionalViolationError evolved
  from a bare Exception(string) into a structured exception carrying a
  list of ViolationReport objects. The autogen vintage instantiated it
  with raw strings and reached for a ``.message`` attribute — neither
  shape exists on the current class. Tests rewritten to:
    * construct with ``[ViolationReport(...)]`` (the canonical contract)
    * assert on ``str(err)`` matching ``"Blocked by IntentGuard: <msg>"``
      (the legacy str-form preserved across the rewrite for handler
      compatibility — see source's docstring contract)
    * read structured state via ``err.violations`` instead of ``.message``
    * pin the empty-violations case to the "constitutional rule violated"
      fallback the source emits when the violations list is empty.
"""

import pytest

from mind.governance.violation_report import (
    ConstitutionalViolationError,
    ViolationReport,
)


def _make_violation(message: str = "Test violation") -> ViolationReport:
    """Tiny factory — ViolationReport is a dataclass and all fields except
    ``suggested_fix`` and ``source_policy`` are required positionals."""
    return ViolationReport(
        rule_name="test_rule",
        path="src/test.py",
        message=message,
        severity="critical",
    )


def test_constitutional_violation_error_is_exception_subclass():
    """ConstitutionalViolationError inherits from ValueError (and thus
    Exception) — historical compatibility preserved across the rewrite."""
    assert issubclass(ConstitutionalViolationError, Exception)
    assert issubclass(ConstitutionalViolationError, ValueError)


def test_constitutional_violation_error_instantiation_with_message():
    """The error's str-form is the legacy ``"Blocked by IntentGuard: <msg>"``
    one-liner derived from the first violation's message — preserved so
    handlers stringifying the exception (e.g. for ActionResult.data["error"])
    keep their byte-identical output."""
    violation = _make_violation(message="Change violates policy 42")
    error_instance = ConstitutionalViolationError([violation])
    assert str(error_instance) == "Blocked by IntentGuard: Change violates policy 42"
    assert error_instance.violations == [violation]


def test_constitutional_violation_error_instantiation_without_message():
    """An empty violations list still yields a constructable error; the
    str-form falls back to the ``"constitutional rule violated"`` literal."""
    error_instance = ConstitutionalViolationError([])
    assert str(error_instance) == "Blocked by IntentGuard: constitutional rule violated"
    assert error_instance.violations == []


def test_constitutional_violation_error_inherits_exception_behavior():
    """Raising and catching by the specific type works exactly like a
    regular Exception."""
    violation = _make_violation(message="Test violation")
    try:
        raise ConstitutionalViolationError([violation])
    except ConstitutionalViolationError as e:
        assert str(e) == "Blocked by IntentGuard: Test violation"
    except Exception:
        pytest.fail(
            "ConstitutionalViolationError should be caught by its own type, "
            "not a generic Exception."
        )


def test_constitutional_violation_error_carries_structured_violations():
    """Multiple violations are preserved on ``.violations`` and surface
    through ``to_dict()`` for JSON-safe persistence into execution_results."""
    violations = [
        _make_violation(message="First violation"),
        _make_violation(message="Second violation"),
    ]
    error = ConstitutionalViolationError(violations)
    assert len(error.violations) == 2
    payload = error.to_dict()
    assert payload["violation_count"] == 2
    assert payload["blocked_by"] == "IntentGuard"
    assert {v["message"] for v in payload["violations"]} == {
        "First violation",
        "Second violation",
    }
