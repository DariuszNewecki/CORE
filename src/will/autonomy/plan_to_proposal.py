# src/will/autonomy/plan_to_proposal.py
"""Bridge: PlannerAgent execution plan -> Proposal shape (ADR-160 D3).

`PlannerAgent.create_execution_plan()` produces `list[ExecutionTask]` for
direct `ActionExecutor` dispatch via `DetailedPlanStep.from_execution_task`
(`shared/models/workflow_models.py:105`). Nothing converted that plan into
the `ProposalScope` + `list[ProposalAction]` shape `Proposal.compute_risk()`
and `safe_auto_approval_envelope.validate_envelope()` operate on -- this
module is that bridge, built for ADR-160 D3's first staged conversion
(`POST /develop/goal` / `develop_from_goal`'s `create_proposal_only` mode).

Fail-closed throughout: any plan this converter cannot represent faithfully
as a Proposal is a refusal, never a partial or best-effort Proposal.
Refusing is cheap and reversible; a Proposal that understates or drops a
planned target is not.
"""

from __future__ import annotations

from shared.exceptions import CoreError
from shared.models.execution_models import ExecutionTask
from will.autonomy.proposal import (
    _SCOPE_FILES_MAX_ITEMS,
    ProposalAction,
    ProposalScope,
)


# ID: 182c6297-d0bc-49f8-b899-35647f371661
class PlanConversionRefused(CoreError):
    """A planner-produced execution plan cannot be faithfully represented
    as a Proposal.

    Raised instead of emitting a partial, truncated, or best-guess
    Proposal -- per ADR-160 D3, a conversion the bridge cannot perform
    faithfully must refuse, not degrade silently.
    """


# `refactor_modularity` bypasses the planner's own action choice entirely:
# `code_generation_phase.py`'s `execute()` routes to `_execute_deterministic_split`
# unconditionally for this workflow_type (line 92-93), which always dispatches
# `refactor.apply_split` via `ModularitySplitter` regardless of what
# `PlannerAgent.create_execution_plan()` proposed. Converting the *planned*
# tasks into a Proposal for this workflow_type would describe actions that
# will never execute and omit the one that will -- refuse rather than
# construct a Proposal that misrepresents the run.
_WORKFLOW_TYPES_PLAN_DESCRIBES_EXECUTION = frozenset(
    {"code_modification", "coverage_remediation"}
)


# ID: 7cac4c39-394a-4f48-8f80-158a1e05eb0e
def convert_execution_plan(
    tasks: list[ExecutionTask], *, workflow_type: str
) -> tuple[ProposalScope, list[ProposalAction]]:
    """Convert a PlannerAgent execution plan into a ProposalScope + actions.

    Raises PlanConversionRefused -- never returns a partial result -- when:
    - `workflow_type` is one whose actual execution path does not follow
      the planned tasks (currently: `refactor_modularity`);
    - the plan is empty;
    - any task has no resolvable file target (`params.file_path` unset);
    - the resulting scope would exceed `Proposal`'s own constitutional
      blast bound (`_SCOPE_FILES_MAX_ITEMS`, `proposal.py:42`).

    `ProposalScope.files` is built as the exact set of action target files
    by construction (not by convention) -- `validate_envelope()` rejects any
    mismatch between the two, so this bridge must not be able to produce one.
    """
    if workflow_type not in _WORKFLOW_TYPES_PLAN_DESCRIBES_EXECUTION:
        raise PlanConversionRefused(
            f"workflow_type {workflow_type!r} does not execute the planned "
            "tasks as proposed (e.g. refactor_modularity always dispatches "
            "a deterministic split regardless of the plan) -- converting "
            "the plan to a Proposal would misrepresent what will run"
        )

    if not tasks:
        raise PlanConversionRefused("plan is empty -- nothing to propose")

    actions: list[ProposalAction] = []
    target_files: set[str] = set()

    for order, task in enumerate(tasks):
        file_path = task.params.file_path
        if not file_path or not isinstance(file_path, str):
            raise PlanConversionRefused(
                f"task {order} (action={task.action!r}, step={task.step!r}) "
                "has no resolvable file target -- refusing rather than "
                "emitting a Proposal with an incomplete scope"
            )

        parameters = task.params.model_dump(exclude_none=True)
        actions.append(
            ProposalAction(action_id=task.action, parameters=parameters, order=order)
        )
        target_files.add(file_path)

    if len(target_files) > _SCOPE_FILES_MAX_ITEMS:
        raise PlanConversionRefused(
            f"plan targets {len(target_files)} distinct files, exceeding "
            f"the constitutional blast bound of {_SCOPE_FILES_MAX_ITEMS} "
            "(ProposalScope.json files.maxItems) -- refusing rather than "
            "truncating, splitting, or dropping targets"
        )

    return ProposalScope(files=sorted(target_files)), actions
