"""planning.no_code_generation fixture pair (#849, #842 G2 fixture-coverage program).

The rule's mapped mechanism, ``base_planner.parse_and_validate_plan``, checks
``if params.get("code"):`` -- a truthiness test, not ``is not None``. #849 found
the rule statement said "MUST be None" while the deployed check always treated
an empty string as compliant. The governor's ruling (#849) is that the
truthy-only check is the correct, intended law -- non-empty code is
prohibited, empty string and null are both compliant -- and the rule statement
was corrected to match rather than tightening the runtime guard. These tests
prove that reading against the real ``parse_and_validate_plan`` dispatch path,
never mocked: substantive code must fail, empty string and null must pass.
"""

from __future__ import annotations

import json

import pytest

from shared.models import ExecutionTask, PlanExecutionError
from will.agents.base_planner import parse_and_validate_plan


def _plan_response(code: str | None, omit_code_key: bool = False) -> str:
    params: dict[str, object] = {"file_path": "src/greeting.py"}
    if not omit_code_key:
        params["code"] = code
    task = {
        "step": "Create the greeting module",
        "action": "create_file",
        "params": params,
    }
    return json.dumps([task])


def test_no_code_generation_fires_on_substantive_code() -> None:
    """Violating fixture: non-empty code in params.code MUST be rejected."""
    response_text = _plan_response("def greet():\n    return 'hi'\n")

    with pytest.raises(PlanExecutionError) as excinfo:
        parse_and_validate_plan(response_text)

    assert "planning.no_code_generation" in str(excinfo.value)


def test_no_code_generation_passes_for_empty_and_null_code() -> None:
    """Compliant fixture: empty string and null in params.code are both accepted."""
    empty_string_plan = parse_and_validate_plan(_plan_response(""))
    assert len(empty_string_plan) == 1
    assert isinstance(empty_string_plan[0], ExecutionTask)
    assert empty_string_plan[0].params.code == ""

    null_plan = parse_and_validate_plan(_plan_response(None))
    assert len(null_plan) == 1
    assert null_plan[0].params.code is None
