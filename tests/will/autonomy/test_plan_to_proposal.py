# tests/will/autonomy/test_plan_to_proposal.py
"""convert_execution_plan — the ADR-160 D3 bridge from PlannerAgent's
`list[ExecutionTask]` to `ProposalScope` + `list[ProposalAction]`.

Fail-closed by design: every branch that cannot faithfully represent the
plan raises `PlanConversionRefused` rather than returning a partial or
truncated result. No DB, no LLM — pure data transformation.
"""

from __future__ import annotations

import pytest

from shared.models.execution_models import ExecutionTask, TaskParams
from will.autonomy.plan_to_proposal import (
    PlanConversionRefused,
    convert_execution_plan,
)
from will.autonomy.proposal import _SCOPE_FILES_MAX_ITEMS


def _task(action: str, file_path: str | None, step: str = "step") -> ExecutionTask:
    return ExecutionTask(
        step=step,
        action=action,
        params=TaskParams(file_path=file_path),
        task_type="code_generation",
    )


# --------------------------------------------------------------------- success


def test_converts_plan_to_scope_and_actions_with_exact_consistency() -> None:
    plan = [
        _task("file.edit", "src/foo.py"),
        _task("file.create", "src/bar.py"),
    ]

    scope, actions = convert_execution_plan(plan, workflow_type="code_modification")

    assert scope.files == ["src/bar.py", "src/foo.py"]
    assert {a.action_id for a in actions} == {"file.edit", "file.create"}
    # Anti-drift property: scope.files is exactly the set of action targets.
    action_targets = {a.parameters["file_path"] for a in actions}
    assert set(scope.files) == action_targets
    for action in actions:
        assert isinstance(action.parameters["file_path"], str)


def test_two_tasks_targeting_the_same_file_dedupe_in_scope_not_actions() -> None:
    plan = [
        _task("file.edit", "src/foo.py", step="first edit"),
        _task("file.edit", "src/foo.py", step="second edit"),
    ]

    scope, actions = convert_execution_plan(plan, workflow_type="code_modification")

    assert scope.files == ["src/foo.py"]
    assert len(actions) == 2  # both actions preserved
    assert {a.parameters["file_path"] for a in actions} == {"src/foo.py"}


def test_coverage_remediation_workflow_type_is_accepted() -> None:
    plan = [_task("build.test_for_symbol", "tests/test_foo.py")]

    scope, actions = convert_execution_plan(plan, workflow_type="coverage_remediation")

    assert scope.files == ["tests/test_foo.py"]
    assert len(actions) == 1


def test_action_order_is_preserved() -> None:
    plan = [
        _task("file.create", "src/a.py"),
        _task("file.edit", "src/b.py"),
        _task("file.edit", "src/c.py"),
    ]

    _, actions = convert_execution_plan(plan, workflow_type="code_modification")

    assert [a.order for a in actions] == [0, 1, 2]
    assert [a.parameters["file_path"] for a in actions] == [
        "src/a.py",
        "src/b.py",
        "src/c.py",
    ]


# --------------------------------------------------------------------- refusals


def test_refuses_refactor_modularity_workflow_type() -> None:
    """The deterministic split path bypasses the planner's own action
    choice entirely (code_generation_phase.py:92-93) — the plan does not
    describe what will actually execute, so conversion must refuse."""
    plan = [_task("refactor.apply_split", "src/big_file.py")]

    with pytest.raises(PlanConversionRefused, match="refactor_modularity"):
        convert_execution_plan(plan, workflow_type="refactor_modularity")


def test_refuses_empty_plan() -> None:
    with pytest.raises(PlanConversionRefused, match="empty"):
        convert_execution_plan([], workflow_type="code_modification")


def test_refuses_task_with_no_resolvable_file_target() -> None:
    plan = [
        _task("file.edit", "src/foo.py"),
        _task("file.edit", None),
    ]

    with pytest.raises(PlanConversionRefused, match="no resolvable file target"):
        convert_execution_plan(plan, workflow_type="code_modification")


def test_refuses_when_scope_exceeds_max_items() -> None:
    plan = [
        _task("file.edit", f"src/file_{i}.py")
        for i in range(_SCOPE_FILES_MAX_ITEMS + 1)
    ]

    with pytest.raises(PlanConversionRefused, match="exceeding"):
        convert_execution_plan(plan, workflow_type="code_modification")


def test_does_not_truncate_or_drop_targets_when_refusing_over_cap() -> None:
    """The refusal message states the true count -- proof nothing was
    silently truncated before the refusal was raised."""
    count = _SCOPE_FILES_MAX_ITEMS + 5
    plan = [_task("file.edit", f"src/file_{i}.py") for i in range(count)]

    with pytest.raises(PlanConversionRefused, match=str(count)):
        convert_execution_plan(plan, workflow_type="code_modification")
