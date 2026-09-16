# tests/will/agents/test_investigation_planner.py

"""The investigation plan validator refuses anything that is not read-only (#895 U2)."""

from __future__ import annotations

import json

import pytest

from will.agents.investigation_planner import (
    INVESTIGATION_STEP_VOCABULARY,
    InvestigationPlanError,
    parse_and_validate_investigation_plan,
    validate_investigation_plan,
)


def _step(action: str, step: str = "look at something", **params: object) -> dict:
    return {"action": action, "step": step, "params": params}


def test_accepts_a_plan_drawn_from_the_closed_vocabulary() -> None:
    steps = validate_investigation_plan(
        [_step("inspect.layout"), _step("inspect.path", path="README.md")]
    )

    assert [s.action for s in steps] == ["inspect.layout", "inspect.path"]
    assert steps[1].params == {"path": "README.md"}


def test_the_vocabulary_is_closed() -> None:
    """An unrecognised step is refused, not ignored."""
    with pytest.raises(InvestigationPlanError) as exc:
        validate_investigation_plan([_step("inspect.everything")])

    assert "outside the closed investigation vocabulary" in str(exc.value)


@pytest.mark.parametrize(
    "action",
    ["file.create", "file.edit", "fix.imports", "sync.db", "build.tests", "commit.now"],
)
def test_a_mutating_action_rejects_the_whole_plan(action: str) -> None:
    """Not filtered out — the attempt is itself evidence and must not vanish."""
    plan = [_step("inspect.layout"), _step(action)]

    with pytest.raises(InvestigationPlanError) as exc:
        validate_investigation_plan(plan)

    assert "mutates the target" in str(exc.value)


def test_a_mutating_description_is_caught_even_with_a_read_only_action() -> None:
    """A model can dodge the action name while stating mutating intent."""
    with pytest.raises(InvestigationPlanError) as exc:
        validate_investigation_plan(
            [_step("inspect.path", step="rewrite the config file", path="cfg.yaml")]
        )

    assert "mutates the target" in str(exc.value)


def test_an_empty_plan_is_refused() -> None:
    with pytest.raises(InvestigationPlanError) as exc:
        validate_investigation_plan([])

    assert "produce findings about nothing" in str(exc.value)


def test_non_object_step_is_refused() -> None:
    with pytest.raises(InvestigationPlanError):
        validate_investigation_plan(["inspect.layout"])


def test_non_object_params_are_refused() -> None:
    with pytest.raises(InvestigationPlanError) as exc:
        validate_investigation_plan(
            [{"action": "inspect.layout", "step": "look", "params": ["a"]}]
        )

    assert "non-object params" in str(exc.value)


def test_parses_the_wrapped_plan_shape() -> None:
    response = json.dumps({"plan": [_step("inspect.artifact_types")]})

    steps = parse_and_validate_investigation_plan(response)

    assert [s.action for s in steps] == ["inspect.artifact_types"]


def test_unparseable_output_is_refused() -> None:
    with pytest.raises(InvestigationPlanError):
        parse_and_validate_investigation_plan("not json at all")


def test_vocabulary_contains_no_mutating_entry() -> None:
    """Guard on the vocabulary itself, not only on plans that use it."""
    forbidden_prefixes = ("file.", "fix.", "sync.", "build.", "commit.", "execution.")

    for action in INVESTIGATION_STEP_VOCABULARY:
        assert not action.startswith(forbidden_prefixes), action
        assert action.startswith("inspect."), action
