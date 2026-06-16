# src/will/agents/strategic_auditor/agent.py

"""
StrategicAuditor — CORE's self-awareness agent.

Reads full system state, reasons about it as a whole, produces a prioritised
remediation campaign, and executes what is constitutionally permitted.

Constitutional role:
- Reads everything (audit, DB, .intent/, git) — never writes to .intent/
- Flags anything requiring .intent/ amendment as escalation (requires_approval=True)
- Executes autonomous tasks via develop_from_goal

This module is the orchestration shell plus human/machine rendering. The
LLM-driven campaign synthesis lives in reasoning.py; the side effects
(persistence to the task DB, dispatch to autonomous_developer) live in
effects.py. SystemContextGatherer (context_gatherer.py) and the dataclasses
(models.py) are pre-existing collaborators in this package.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from shared.logger import getLogger
from will.agents.strategic_auditor.context_gatherer import SystemContextGatherer
from will.agents.strategic_auditor.effects import (
    execute_autonomous_tasks,
    persist_campaign,
)
from will.agents.strategic_auditor.models import StrategicCampaign
from will.agents.strategic_auditor.reasoning import synthesize_campaign
from will.agents.traced_agent_mixin import TracedAgentMixin
from will.orchestration.decision_tracer import DecisionTracer


if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from shared.context import CoreContext
    from will.orchestration.cognitive_service import CognitiveService


logger = getLogger(__name__)


# ID: 752c04d3-2c98-4847-a256-1271ef60f6c4
class StrategicAuditor(TracedAgentMixin):
    """
    CORE's self-awareness agent.

    Reads full system state, reasons about it as a whole, produces a
    prioritised remediation campaign, and executes what it constitutionally can.

    Enforcement tiers respected:
    - Never touches .intent/ (hard invariant)
    - Flags constitution changes as escalations (requires_approval=True)
    - Executes only tasks within existing workflow types
    """

    def __init__(self, context: CoreContext, cognitive_service: CognitiveService):
        self._ctx = context
        self._cognitive = cognitive_service
        self.tracer = DecisionTracer(context.path_resolver)

    # ID: 694a9c0f-327b-45a8-873c-e318ce467335
    async def run(
        self,
        session: AsyncSession,
        write: bool = False,
        execute_autonomous: bool = False,
    ) -> StrategicCampaign:
        """
        Execute a full strategic audit cycle.

        Args:
            session: Database session
            write: Persist campaign to PostgreSQL
            execute_autonomous: Immediately execute non-escalation tasks (implies write)

        Returns:
            StrategicCampaign with clusters, escalations, and human report
        """
        logger.info("=" * 70)
        logger.info("STRATEGIC AUDIT — CORE Self-Awareness Cycle")
        logger.info("=" * 70)

        gatherer = SystemContextGatherer(self._ctx, self._cognitive)
        system_context = await gatherer.gather(session)

        campaign = await synthesize_campaign(self._cognitive, system_context)

        if write:
            await persist_campaign(session, campaign)

        if write and execute_autonomous:
            await execute_autonomous_tasks(self._ctx, campaign)

        self._log_summary(campaign)

        self.tracer.record(
            agent="StrategicAuditor",
            decision_type="strategic_audit",
            rationale="Full system state analysis",
            chosen_action=(
                f"Produced campaign with {len(campaign.clusters)} autonomous + "
                f"{len(campaign.escalations)} escalation tasks"
            ),
            context={
                "total_findings": campaign.total_findings,
                "autonomous_tasks": campaign.autonomous_task_count,
                "escalations": campaign.escalation_count,
                "write": write,
            },
            confidence=0.9,
        )

        return campaign

    # ID: eb28a664-23c1-4b84-84b8-e67ed158b364
    def _log_summary(self, campaign: StrategicCampaign) -> None:
        """Print human-readable campaign summary to console."""
        logger.info("")
        logger.info("=" * 70)
        logger.info("STRATEGIC AUDIT RESULTS")
        logger.info("=" * 70)
        logger.info("")
        logger.info("SYSTEM ASSESSMENT:")
        logger.info("%s", campaign.system_summary)
        logger.info("")
        logger.info(
            "FINDINGS: %d total — %d root cause clusters — %d escalations",
            campaign.total_findings,
            campaign.autonomous_task_count,
            campaign.escalation_count,
        )
        logger.info("")

        if campaign.clusters:
            logger.info("AUTONOMOUS REMEDIATION PLAN:")
            for i, c in enumerate(campaign.clusters, 1):
                logger.info(
                    "  %d. [%s impact, %.0f%% confidence] %s",
                    i,
                    c.estimated_impact.upper(),
                    c.confidence * 100,
                    c.root_cause,
                )
                logger.info("     Fix: %s", c.proposed_fix[:120])

        if campaign.escalations:
            logger.info("")
            logger.info(
                "ESCALATIONS (require your review — .intent/ amendment needed):"
            )
            for i, c in enumerate(campaign.escalations, 1):
                logger.info("  %d. %s", i, c.root_cause)
                logger.info("     Amendment needed: %s", c.proposed_fix[:120])

        logger.info("")
        logger.info("Campaign ID: %s", campaign.campaign_id)
        logger.info("=" * 70)

    # ID: 25cb5939-6994-4188-8ae5-4125da222cb8
    def format_machine(self, campaign: StrategicCampaign) -> dict[str, Any]:
        """Machine-readable campaign representation for LLM consumption or API."""
        return {
            "campaign_id": campaign.campaign_id,
            "created_at": campaign.created_at.isoformat(),
            "system_summary": campaign.system_summary,
            "stats": {
                "total_findings": campaign.total_findings,
                "autonomous_tasks": campaign.autonomous_task_count,
                "escalations": campaign.escalation_count,
            },
            "autonomous_clusters": [
                {
                    "cluster_id": c.cluster_id,
                    "root_cause": c.root_cause,
                    "proposed_fix": c.proposed_fix,
                    "affected_files": c.affected_files,
                    "finding_ids": c.finding_ids,
                    "confidence": c.confidence,
                    "estimated_impact": c.estimated_impact,
                    "workflow_type": c.workflow_type,
                }
                for c in campaign.clusters
            ],
            "escalations": [
                {
                    "cluster_id": c.cluster_id,
                    "root_cause": c.root_cause,
                    "constitutional_amendment_needed": c.proposed_fix,
                    "affected_files": c.affected_files,
                    "confidence": c.confidence,
                }
                for c in campaign.escalations
            ],
        }
