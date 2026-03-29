# src/will/workers/proposal_worker.py
# ID: will.workers.proposal_worker

"""
AutonomousProposalWorker — A3 bridge between sensing and action.

Reads recent ERROR-level audit findings from core.audit_findings, reasons
about each group via PromptModel, and creates Proposal objects in
ProposalRepository. Safe proposals (approval_required=False) are created in
APPROVED status so ProposalConsumerWorker can execute them immediately.
Proposals requiring human approval are created in DRAFT.

Dry-run by default (config.write=false in .intent/workers/proposal_worker.yaml):
  - Builds and validates the Proposal object
  - Does NOT save to DB
  - Posts "proposal_worker.proposal_pending" to Blackboard for visibility

Write mode (config.write=true):
  - Saves Proposal to DB
  - Posts "proposal_worker.proposal_submitted" to Blackboard

Constitutional alignment:
  - Extends Worker base class — constitutional standing via .intent/workers/proposal_worker.yaml
  - All LLM calls via PromptModel.invoke() (ai.prompt.model_required)
  - LLM client resolved via core_context.cognitive_service (no direct instantiation)
  - PromptModel.load() inside run(), never at module level
  - No direct file writes — proposals execute via ProposalConsumerWorker → ProposalExecutor
  - Config read from YAML declaration (self._declaration["config"]), not injected externally
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from shared.logger import getLogger
from shared.workers.base import Worker


logger = getLogger(__name__)

_WORKER_ID = "proposal_worker"

# Maps workflow_type (from PromptModel) → ordered list of action_ids from registry.
# Keep conservative — only well-known safe actions.
_WORKFLOW_ACTIONS: dict[str, list[str]] = {
    "refactor_modularity": ["fix.format", "fix.headers", "fix.docstrings"],
    "coverage_remediation": ["fix.format", "fix.ids"],
    "full_feature_development": ["fix.format", "fix.ids", "fix.headers"],
}


# ID: will.workers.proposal_worker.AutonomousProposalWorker
# ID: 46d4fb89-4bd4-4c68-9086-a39e0563bb01
class AutonomousProposalWorker(Worker):
    """
    Autonomous proposal generator. Reads audit findings, reasons about
    actionability via PromptModel.invoke(), and submits proposals to
    ProposalRepository for ProposalConsumerWorker to execute.

    Extends Worker base class — constitutional standing is declared in
    .intent/workers/proposal_worker.yaml.

    Requires core_context for cognitive_service (LLM client resolution).

    Configuration is read from the YAML declaration's `config` block:
      write: false                  # Set true to persist proposals to DB
      max_proposals_per_run: 3
      lookback_minutes: 60
      prompt_model: proposal_reasoner
    """

    declaration_name = "proposal_worker"

    def __init__(
        self, core_context: Any, declaration_name: str = "", **kwargs: Any
    ) -> None:
        super().__init__(
            declaration_name=declaration_name or self.__class__.declaration_name
        )
        self._ctx = core_context
        # Config comes from the YAML declaration — stable, no external injection needed.
        self._config: dict[str, Any] = self._declaration.get("config", {})

    # ID: will.workers.proposal_worker.run
    # ID: af0a5bb4-659d-4166-a0df-665f8186634a
    async def run(self) -> None:
        """Main entry point called by the Daemon scheduler."""
        from shared.ai.prompt_model import PromptModel

        write: bool = self._config.get("write", False)
        max_proposals: int = self._config.get("max_proposals_per_run", 3)
        lookback_minutes: int = self._config.get("lookback_minutes", 60)
        prompt_model_name: str = self._config.get("prompt_model", "proposal_reasoner")

        logger.info(
            "AutonomousProposalWorker starting (write=%s, max=%s, lookback=%sm)",
            write,
            max_proposals,
            lookback_minutes,
        )

        # Load PromptModel — never at module level
        prompt_model = PromptModel.load(prompt_model_name)

        # Resolve LLM client via cognitive_service
        cognitive = self._ctx.cognitive_service
        if cognitive is None:
            logger.warning(
                "AutonomousProposalWorker: cognitive_service unavailable — skipping run."
            )
            await self.post_report(
                subject="proposal_worker.no_signals",
                payload={"reason": "cognitive_service_unavailable"},
            )
            return

        client = await cognitive.aget_client_for_role(
            prompt_model._artifact.manifest.role
        )

        # 1. Read recent ERROR findings from audit history
        finding_groups = await _read_recent_findings(lookback_minutes)

        if not finding_groups:
            logger.info("No actionable findings in last %sm.", lookback_minutes)
            await self.post_report(
                subject="proposal_worker.no_signals",
                payload={"lookback_minutes": lookback_minutes},
            )
            return

        logger.info("Found %s finding groups to evaluate.", len(finding_groups))

        proposals_created = 0

        for group in finding_groups[:max_proposals]:
            result = await _evaluate_group(
                group=group,
                prompt_model=prompt_model,
                client=client,
            )

            if not result.get("actionable"):
                logger.info(
                    "Group '%s' non-actionable: %s",
                    group["check_id"],
                    result.get("rationale", ""),
                )
                continue

            goal: str = result["goal"]
            workflow_type: str = result.get("workflow_type", "refactor_modularity")
            rationale: str = result.get("rationale", "")

            proposal = _build_proposal(
                goal=goal,
                workflow_type=workflow_type,
                group=group,
                rationale=rationale,
            )

            # Validate before touching anything
            is_valid, errors = proposal.validate()
            if not is_valid:
                logger.warning(
                    "Proposal for '%s' failed validation: %s",
                    group["check_id"],
                    errors,
                )
                continue

            if write:
                from shared.infrastructure.database.session_manager import get_session

                async with get_session() as session:
                    from will.autonomy.proposal_repository import ProposalRepository

                    repo = ProposalRepository(session)
                    await repo.create(proposal)

                await self.post_report(
                    subject="proposal_worker.proposal_submitted",
                    payload={
                        "proposal_id": proposal.proposal_id,
                        "goal": goal,
                        "workflow_type": workflow_type,
                        "check_id": group["check_id"],
                        "status": proposal.status.value,
                        "approval_required": proposal.approval_required,
                    },
                )
                logger.info(
                    "Proposal submitted: %s → '%s' (status=%s, approval_required=%s)",
                    proposal.proposal_id,
                    goal,
                    proposal.status.value,
                    proposal.approval_required,
                )
            else:
                await self.post_report(
                    subject="proposal_worker.proposal_pending",
                    payload={
                        "proposal_id": proposal.proposal_id,
                        "goal": goal,
                        "workflow_type": workflow_type,
                        "rationale": rationale,
                        "check_id": group["check_id"],
                        "affected_files": group.get("files", []),
                        "risk": (
                            proposal.risk.overall_risk if proposal.risk else "unknown"
                        ),
                        "approval_required": proposal.approval_required,
                        "dry_run": True,
                    },
                )
                logger.info(
                    "[DRY-RUN] Proposal pending: %s → '%s' (risk=%s, status=%s)",
                    proposal.proposal_id,
                    goal,
                    proposal.risk.overall_risk if proposal.risk else "unknown",
                    proposal.status.value,
                )

            proposals_created += 1

        logger.info(
            "AutonomousProposalWorker done. %s/%s proposals generated.",
            proposals_created,
            len(finding_groups[:max_proposals]),
        )


# ─── Private helpers ──────────────────────────────────────────────────────────


def _build_proposal(
    goal: str,
    workflow_type: str,
    group: dict[str, Any],
    rationale: str,
) -> Any:
    """
    Construct a Proposal with computed risk and appropriate initial status.

    Safe proposals (approval_required=False) are created in APPROVED status
    so ProposalConsumerWorker can pick them up without a separate approval step.
    Proposals requiring human approval are created in DRAFT.
    """
    from will.autonomy.proposal import (
        Proposal,
        ProposalAction,
        ProposalScope,
        ProposalStatus,
    )

    action_ids = _WORKFLOW_ACTIONS.get(workflow_type, ["fix.format"])

    actions = [
        ProposalAction(action_id=action_id, parameters={}, order=i)
        for i, action_id in enumerate(action_ids)
    ]

    proposal = Proposal(
        proposal_id=f"auto-{uuid.uuid4().hex[:8]}",
        goal=goal,
        actions=actions,
        scope=ProposalScope(files=group.get("files", []), modules=[]),
        status=ProposalStatus.DRAFT,
        created_by=_WORKER_ID,
        constitutional_constraints={
            "source_check_id": group["check_id"],
            "rationale": rationale,
            "violation_count": group["count"],
        },
    )

    proposal.compute_risk()

    if not proposal.approval_required:
        proposal.status = ProposalStatus.APPROVED

    return proposal


async def _read_recent_findings(lookback_minutes: int) -> list[dict[str, Any]]:
    """
    Query core.audit_findings for recent ERROR-level violations grouped by check_id.
    """
    from body.services.service_registry import service_registry

    svc = await service_registry.get_audit_findings_service()
    return await svc.fetch_recent_error_findings(lookback_minutes)


async def _evaluate_group(
    group: dict[str, Any],
    prompt_model: Any,
    client: Any,
) -> dict[str, Any]:
    """
    Ask PromptModel whether this finding group is autonomously actionable.

    Expected structured response:
        {
            "actionable": bool,
            "goal": str,
            "workflow_type": str,
            "rationale": str,
        }

    Behaviour:
    - First expects valid JSON from the model
    - Falls back safely to non-actionable on parse/validation failure
    - Normalizes missing fields so callers can rely on stable keys
    """
    from shared.ai.response_parser import extract_json_safe

    try:
        raw_response = await prompt_model.invoke(
            context={"violations": json.dumps(group, indent=2)},
            client=client,
            user_id=_WORKER_ID,
        )

        parsed = extract_json_safe(raw_response)

        if not isinstance(parsed, dict):
            logger.warning(
                "Proposal evaluation for %s did not return a JSON object.",
                group["check_id"],
            )
            return {"actionable": False, "rationale": "invalid_response_shape"}

        actionable = parsed.get("actionable", False)
        goal = parsed.get("goal", "")
        workflow_type = parsed.get("workflow_type")
        rationale = parsed.get("rationale", "")

        if not isinstance(actionable, bool):
            logger.warning(
                "Proposal evaluation for %s returned non-boolean 'actionable'.",
                group["check_id"],
            )
            return {"actionable": False, "rationale": "invalid_actionable_type"}

        if actionable and not isinstance(goal, str):
            logger.warning(
                "Proposal evaluation for %s returned invalid 'goal' type.",
                group["check_id"],
            )
            return {"actionable": False, "rationale": "invalid_goal_type"}

        if not workflow_type or not isinstance(workflow_type, str):
            logger.warning(
                "Proposal evaluation for %s missing valid workflow_type.",
                group["check_id"],
            )
            return {"actionable": False, "rationale": "missing_workflow_type"}

        if not isinstance(rationale, str):
            rationale = ""

        workflow_type = workflow_type.strip()
        if not workflow_type:
            logger.warning(
                "Proposal evaluation for %s missing valid workflow_type.",
                group["check_id"],
            )
            return {"actionable": False, "rationale": "missing_workflow_type"}

        return {
            "actionable": actionable,
            "goal": goal.strip(),
            "workflow_type": workflow_type,
            "rationale": rationale.strip(),
        }

    except Exception as exc:
        logger.warning(
            "PromptModel evaluation failed for %s: %s",
            group["check_id"],
            exc,
        )

    return {"actionable": False, "rationale": "evaluation_error"}
