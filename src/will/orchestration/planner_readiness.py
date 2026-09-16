# src/will/orchestration/planner_readiness.py
"""
Planner readiness probe (#894 Unit 3; ADR-159 remediation item 3, explicit
unavailability).

Answers one question before a goal-driven run plans anything: can the
planner obtain what it needs from the bound environment -- its governed
prompt (resolved under the bound repository's prompt root) and a client
for its cognitive role (resolved from the bound database's role/resource
assignments)? If not, the answer is a reason string the caller records as
an *unavailable* instrument result -- "could not look", distinct from
"looked and failed". Called by GoalExecutionWorker only; the external-run
route does not probe on its own, because Blackboard recording belongs to
the Worker.
"""

from __future__ import annotations

from typing import Any

from shared.logger import getLogger


logger = getLogger(__name__)

PLANNER_PROMPT_ID = "plan_goal"


# ID: a481d399-10a1-48be-93c7-4d68b2434cd5
async def resolve_brain_services(context: Any) -> None:
    """Warm up the cognitive service and auditor context on *context*.

    The same resolves `@core_command(requires_context=True)` performs for a
    CLI-entered run, so a Worker started from any other entry point (the
    pre-bootstrap external-run route, #894) is not short of them.
    CodeGenerationPhase refuses without auditor_context. Failures are
    logged, never raised: readiness is probed separately.
    """
    if context.cognitive_service is None:
        try:
            context.cognitive_service = await context.registry.get_cognitive_service()
        except Exception as exc:
            logger.warning("Could not resolve cognitive_service from registry: %s", exc)
    if getattr(context, "auditor_context", None) is None:
        try:
            context.auditor_context = await context.registry.get_auditor_context()
        except Exception as exc:
            logger.warning("Could not resolve auditor_context from registry: %s", exc)


# ID: 48299632-63d0-48b4-a0fd-c2b15e42809c
async def probe_planner_readiness(context: Any) -> str | None:
    """Return why the planner cannot run in *context*, or None when it can."""
    from shared.ai.prompt_model import PromptModel

    try:
        model = PromptModel.load(PLANNER_PROMPT_ID)
    except Exception as exc:
        return f"planner prompt {PLANNER_PROMPT_ID!r} unavailable under the bound repository: {exc}"
    role = model._artifact.manifest.role
    cognitive = getattr(context, "cognitive_service", None)
    if cognitive is None:
        return "no cognitive_service on the context"
    try:
        await cognitive.aget_client_for_role(role)
    except Exception as exc:
        return (
            f"no cognitive-role client for planner role {role!r} in the bound "
            f"database: {exc}"
        )
    return None
