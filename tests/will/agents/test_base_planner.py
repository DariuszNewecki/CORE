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
from will.agents.base_planner import parse_and_validate_plan, plan_steps


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


# --------------------------------------------------------------------------- plan shape
# The plan_goal artifact asks for {"plan": [...]} (provider JSON-object mode
# constrains the root to an object on Ollama; json_schema is unavailable on
# DeepSeek, #425). Found by the #894 seeded live run: the pinned
# qwen2.5-coder:3b returned a single step OBJECT under `format: json`, three
# attempts out of three, and the old list-only parser failed every run.


def _step(n: int) -> dict[str, object]:
    return {
        "step": f"Change module {n}",
        "action": "file.edit",
        "params": {"file_path": f"src/mod{n}.py"},
    }


def test_wrapper_object_is_the_contract() -> None:
    plan = parse_and_validate_plan(json.dumps({"plan": [_step(1), _step(2)]}))
    assert [t.params.file_path for t in plan] == ["src/mod1.py", "src/mod2.py"]


def test_bare_list_is_still_accepted() -> None:
    """What looser providers returned under the previous `[...]` contract."""
    plan = parse_and_validate_plan(json.dumps([_step(1)]))
    assert len(plan) == 1


@pytest.mark.parametrize(
    "response",
    [
        json.dumps(_step(1)),  # Ollama's coercion of a would-be array
        json.dumps({"plan": _step(1)}),  # wrapper around a non-list
        json.dumps({"steps": [_step(1)]}),  # wrong key
        json.dumps("nope"),
    ],
    ids=["single-step-object", "wrapper-non-list", "wrong-key", "scalar"],
)
def test_non_plan_shapes_are_refused_with_the_contract_named(response: str) -> None:
    with pytest.raises(PlanExecutionError):
        parse_and_validate_plan(response)


def test_plan_steps_unwraps_or_returns_none() -> None:
    assert plan_steps([1, 2]) == [1, 2]
    assert plan_steps({"plan": [1]}) == [1]
    assert plan_steps({"plan": {}}) is None
    assert plan_steps({}) is None
    assert plan_steps(None) is None


def test_artifact_example_parses_under_the_parser() -> None:
    """The example in var/prompts/plan_goal/system.txt IS a valid plan for
    this parser -- the artifact and the parser state one contract."""
    from pathlib import Path

    from shared.utils.parsing import extract_json_from_response

    repo_root = Path(__file__).resolve().parents[3]
    system_txt = (repo_root / "var/prompts/plan_goal/system.txt").read_text()
    example = system_txt.split("EXAMPLE of a valid plan:", 1)[1]
    parsed = extract_json_from_response(example)
    assert isinstance(parsed, dict) and isinstance(parsed.get("plan"), list)
    plan = parse_and_validate_plan(example)
    assert [t.action for t in plan] == ["file.create", "file.edit"]
