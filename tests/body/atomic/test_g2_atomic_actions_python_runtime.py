# tests/body/atomic/test_g2_atomic_actions_python_runtime.py

"""#842 Unit F: python_runtime atomic_actions fixture pairs.

python_runtime resolves through PASSIVE_ALIASES to PassiveGateEngine, not
a firing audit engine (mind/logic/engines/registry.py) -- these rules are
not proven by exercising PassiveGateEngine.verify(), they are proven by
directly exercising each rule's declared `enforcement_location` /
`validation_function`, which are real, callable Python symbols.

- atomic_actions.must_have_decorator, atomic_actions.must_return_action_result
  -> body.atomic.registry._validate_action_signature. Both rules are
  enforced by the same function; distinct violating inputs (missing
  return annotation vs. missing @atomic_action metadata attribute) prove
  each rule separately, per #842's "shared symbols may share fixtures
  only when those assertions separately prove each rule."

- atomic_actions.result_must_be_structured, atomic_actions.no_governance_bypass
  -> body.atomic.executor._validate_action_result. Same pattern: a
  non-dict `.data` proves result_must_be_structured; a non-ActionResult
  return value proves no_governance_bypass. Both violation paths in the
  real function explicitly cite their own rule_violated string, asserted
  here rather than inferred from message text.

atomic_actions.must_accept_kwargs is NOT here -- it already had a real,
precise fixture pair in tests/shared/test_atomic_action__signature_
validation.py (decoration-time TypeError on a **kwargs-less function);
the registry cites that file directly.
"""

from __future__ import annotations

from body.atomic.executor import _validate_action_result
from body.atomic.registry import _validate_action_signature
from shared.action_types import ActionResult


# ---------------------------------------------------------------------------
# _validate_action_signature -- must_have_decorator, must_return_action_result
# ---------------------------------------------------------------------------


def test_missing_decorator_metadata_violates_must_have_decorator() -> None:
    def action_no_decorator(**kwargs) -> ActionResult:
        return ActionResult(action_id="x", ok=True, data={})

    try:
        _validate_action_signature(action_no_decorator)
        raise AssertionError("expected TypeError for missing @atomic_action metadata")
    except TypeError as exc:
        assert "atomic_actions.must_have_decorator" in str(exc)


def test_wrong_return_annotation_violates_must_return_action_result() -> None:
    def action_bad_return(**kwargs) -> bool:
        return True

    action_bad_return._atomic_action_metadata = {}  # satisfy the other check

    try:
        _validate_action_signature(action_bad_return)
        raise AssertionError(
            "expected TypeError for non-ActionResult return annotation"
        )
    except TypeError as exc:
        assert "atomic_actions.must_return_action_result" in str(exc)


def test_correct_signature_passes_both_checks() -> None:
    """Compliant fixture for both must_have_decorator and
    must_return_action_result: a real -> ActionResult annotation plus the
    decorator metadata attribute passes with no exception."""

    def action_ok(**kwargs) -> ActionResult:
        return ActionResult(action_id="x", ok=True, data={})

    action_ok._atomic_action_metadata = {}

    _validate_action_signature(action_ok)  # must not raise


# ---------------------------------------------------------------------------
# _validate_action_result -- result_must_be_structured, no_governance_bypass
# ---------------------------------------------------------------------------


def test_non_dict_data_violates_result_must_be_structured() -> None:
    """.data corrupted to a non-dict after construction (ActionResult's own
    __post_init__ already forbids non-dict data at construction time, so
    this simulates the only realistic way the runtime check's own target
    condition can occur: an action mutating .data after building the
    result)."""
    result = ActionResult(action_id="test.x", ok=True, data={})
    result.data = "not a dict"

    wrapped = _validate_action_result("test.x", result)

    assert wrapped.ok is False
    assert wrapped.data["rule_violated"] == "atomic_actions.result_must_be_structured"


def test_non_action_result_return_violates_no_governance_bypass() -> None:
    tuple_return = (True, "some message")

    wrapped = _validate_action_result("test.x", tuple_return)

    assert wrapped.ok is False
    assert wrapped.data["rule_violated"] == "atomic_actions.no_governance_bypass"


def test_real_action_result_passes_through_unchanged() -> None:
    """Compliant fixture for both result_must_be_structured and
    no_governance_bypass: a genuine ActionResult with dict data is neither
    a bypass (it IS an ActionResult) nor unstructured (data IS a dict)."""
    real = ActionResult(action_id="test.x", ok=True, data={"k": "v"})

    returned = _validate_action_result("test.x", real)

    assert returned is real
    assert returned.ok is True
