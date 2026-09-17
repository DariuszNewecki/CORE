# src/will/agents/investigation_planner.py

"""Closed read-only step vocabulary and plan validator for evaluation (#895 U2).

The symmetric counterpart to ``base_planner``'s Mutation-Only Law. That validator
governs plans that change a target; this one governs plans that only look at one.

Two deliberate differences from the mutation-side validator:

1. **The vocabulary is closed, not open.** A mutation plan may name any
   registered action. An investigation plan may name only the steps listed here,
   because every one of them has to be executable without touching the target.
   An unrecognised step is refused rather than ignored -- "I do not know how to
   do this read-only" is not a safe thing to guess at.

2. **A mutating step rejects the whole plan; it is never filtered out.**
   ``parse_and_validate_plan`` drops offending steps and keeps going. Doing that
   here would leave a clean-looking plan produced by a model that tried to
   mutate the target, and the evidence that it tried would be gone. The attempt
   is the finding.

CONSTITUTIONAL:
- Planning only. Nothing here executes a step, creates a Proposal, or reaches
  ActionExecutor.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from shared.ai.prompt_model import PromptModel
from shared.logger import getLogger
from shared.utils.parsing import extract_json_from_response
from will.agents.base_planner import plan_steps


logger = getLogger(__name__)


# The closed vocabulary. Every entry is answerable by reading already-collected
# reconnaissance or by a bounded read of the bound target copy. Extending this
# set is a deliberate act: a new entry needs a handler that cannot mutate.
INVESTIGATION_STEP_VOCABULARY: frozenset[str] = frozenset(
    {
        "inspect.layout",
        "inspect.artifact_types",
        "inspect.unclassified",
        "inspect.absences",
        "inspect.path",
    }
)

# Steps that announce mutation. Presence of any one of these rejects the plan.
# Matched as a prefix on the action's namespace so a new mutating action in an
# existing family is caught without this list being updated.
_MUTATING_PREFIXES: tuple[str, ...] = (
    "file.",
    "fix.",
    "sync.",
    "change.",
    "commit.",
    "build.",
    "test.",
    "proposal.",
    "execution.",
)

_MUTATING_VERBS: tuple[str, ...] = (
    "write",
    "edit",
    "create",
    "delete",
    "modify",
    "commit",
    "apply",
    "generate",
    "refactor",
    "remove",
)


# ID: 9ebd5c5d-c21e-45f4-a300-d45c27a4b9bb
class InvestigationPlanError(Exception):
    """An investigation plan could not be accepted as read-only."""


@dataclass(frozen=True)
# ID: 597c2e25-d463-4345-93a4-a39866d66130
class InvestigationStep:
    """One validated, read-only step of an investigation plan."""

    step: str
    action: str
    params: dict[str, Any]


# ID: f415d181-32b8-4b28-8baa-13f4cc8fa06d
def validate_investigation_plan(steps: list[Any]) -> list[InvestigationStep]:
    """Accept a plan only if every step is in the closed read-only vocabulary.

    Args:
        steps: Raw step dicts, as produced by the planner.

    Returns:
        The validated steps, in plan order.

    Raises:
        InvestigationPlanError: if the plan is empty, malformed, names a step
            outside the vocabulary, or names anything that mutates.
    """
    if not steps:
        raise InvestigationPlanError(
            "Investigation plan is empty; an evaluation with no steps would "
            "produce findings about nothing."
        )

    validated: list[InvestigationStep] = []

    for index, raw in enumerate(steps, 1):
        if not isinstance(raw, dict):
            raise InvestigationPlanError(
                f"Step {index} is not an object: {type(raw).__name__}."
            )

        action = str(raw.get("action", "")).strip()
        description = str(raw.get("step", "")).strip()

        if _is_mutating(action, description):
            raise InvestigationPlanError(
                f"Step {index} ({action!r}) mutates the target. An investigation "
                "plan is read-only; the whole plan is refused rather than the "
                "step silently dropped, because the attempt is itself evidence."
            )

        if action not in INVESTIGATION_STEP_VOCABULARY:
            raise InvestigationPlanError(
                f"Step {index} names {action!r}, which is outside the closed "
                f"investigation vocabulary {sorted(INVESTIGATION_STEP_VOCABULARY)}."
            )

        params = raw.get("params") or {}
        if not isinstance(params, dict):
            raise InvestigationPlanError(
                f"Step {index} has non-object params: {type(params).__name__}."
            )

        validated.append(
            InvestigationStep(
                step=description or action, action=action, params=dict(params)
            )
        )

    logger.info("Investigation plan accepted: %d read-only steps", len(validated))
    return validated


# ID: 9dc22f89-4ad5-4ab9-83f2-6e5404b87926
def parse_and_validate_investigation_plan(
    response_text: str,
) -> list[InvestigationStep]:
    """Parse a planner response and validate it as read-only.

    Raises:
        InvestigationPlanError: on unparseable output or any validation failure.
    """
    try:
        parsed = extract_json_from_response(response_text)
        steps = plan_steps(parsed)
    except Exception as exc:
        raise InvestigationPlanError(
            f"Investigation plan could not be parsed: {exc}"
        ) from exc

    if steps is None:
        raise InvestigationPlanError(
            'Planner returned no plan: expected {"plan": [...]} or a JSON list.'
        )

    return validate_investigation_plan(steps)


def _is_mutating(action: str, description: str) -> bool:
    """Report whether a step announces mutation, by action or by description.

    Both are checked. A model that avoids a forbidden action name while
    describing the step as "rewrite the config" is still proposing a mutation,
    and the description is the more honest signal of intent.
    """
    lowered_action = action.lower()
    if lowered_action.startswith(_MUTATING_PREFIXES):
        return True

    lowered_description = description.lower()
    return any(verb in lowered_description for verb in _MUTATING_VERBS)


# ID: 364f60d7-7f99-4d7a-8a1d-e950f59b06a3
def investigation_decisions(plan: list[InvestigationStep]) -> list[dict[str, Any]]:
    """The planner's reasoning as structured decision records, one per step.

    Document A A6 asks the run to "record ... its reasoning to the blackboard".
    The mutation planners do that through PlannerAgent's DecisionTracer;
    this planner never touches a tracer, so ParsePhase's mirror found nothing
    and the 2026-09-17 cold run posted no ``goal_run.<id>.decision.<n>`` at
    all. What the planner genuinely decided is on hand: which read-only step
    it chose, the purpose it stated for it, and the closed vocabulary it chose
    from. Nothing else is claimed -- no confidence is invented.
    """
    records: list[dict[str, Any]] = []
    for index, step in enumerate(plan, 1):
        records.append(
            {
                "agent": "investigation_planner",
                "decision_type": "investigation_step_planned",
                "chosen": step.action,
                "rationale": step.step,
                "alternatives": sorted(INVESTIGATION_STEP_VOCABULARY - {step.action}),
                "params": dict(step.params),
                "step_index": index,
            }
        )
    return records


# ID: 74eb4fd7-2d05-4ff0-9413-382ff2f1e329
async def create_investigation_plan(
    cognitive_service: Any,
    goal: str,
    reconnaissance_report: str,
) -> list[InvestigationStep]:
    """Plan a read-only investigation of a target.

    The reconnaissance report is a required argument, not an optional one. An
    evaluation that has not examined its target has nothing to plan against, and
    a plan produced without it would describe an imagined target convincingly.

    Raises:
        InvestigationPlanError: if reconnaissance is missing, the model returns
            nothing, or the returned plan is not read-only.
    """
    if not reconnaissance_report.strip():
        raise InvestigationPlanError(
            "UNAVAILABLE: investigation planning requires a reconnaissance "
            "report; planning blind would describe a target never examined."
        )

    model = PromptModel.load("plan_investigation")
    client = await cognitive_service.aget_client_for_role(model._artifact.manifest.role)

    response_text = await model.invoke(
        context={
            "goal": goal,
            "investigation_step_vocabulary": "\n".join(
                f"- {action}" for action in sorted(INVESTIGATION_STEP_VOCABULARY)
            ),
            "reconnaissance_report": reconnaissance_report,
        },
        client=client,
        user_id="investigation_planner",
    )

    if not response_text:
        raise InvestigationPlanError(
            "UNAVAILABLE: the planner returned no investigation plan."
        )

    return parse_and_validate_investigation_plan(response_text)
