# src/will/agents/strategic_auditor/effects.py

"""
StrategicAuditor — campaign side effects on the world.

Two operations, both gated by StrategicAuditor.run()'s write /
execute_autonomous flags and both taking a finished StrategicCampaign:

- persist_campaign: write a parent Task plus one child Task per
  autonomous cluster and one escalation Task per amendment-required
  cluster, via TaskRepository. Two session commits.
- execute_autonomous_tasks: iterate the campaign's autonomous clusters,
  gate on confidence >= 0.7, dispatch each to develop_from_goal.

Both share one reason to change: how a finished campaign acts on the
system. Splitting them apart would fragment that single answer.

LAYER: will/agents — collaborator of StrategicAuditor. Sessions and
context flow in from the caller; no service-registry session
construction here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from shared.infrastructure.repositories.task_repository import TaskRepository
from shared.logger import getLogger
from will.agents.strategic_auditor.models import StrategicCampaign


if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from shared.context import CoreContext


logger = getLogger(__name__)


# ID: f4d82377-ffce-4794-9bc3-754a48eed83d
async def persist_campaign(session: AsyncSession, campaign: StrategicCampaign) -> None:
    """Store campaign as parent Task + child Tasks in PostgreSQL."""
    repo = TaskRepository(session)

    parent = await repo.create(
        intent=f"[StrategicCampaign:{campaign.campaign_id}] {campaign.system_summary[:200]}",
        assigned_role="StrategicAuditor",
        status="campaign_ready",
    )
    parent.context = {
        "campaign_id": campaign.campaign_id,
        "total_findings": campaign.total_findings,
        "autonomous_tasks": campaign.autonomous_task_count,
        "escalations": campaign.escalation_count,
        "system_summary": campaign.system_summary,
    }
    await session.commit()

    for cluster in campaign.clusters:
        child = await repo.create(
            intent=cluster.proposed_fix,
            assigned_role="AutonomousDeveloper",
            status="pending",
        )
        child.parent_task_id = parent.id
        child.requires_approval = False
        child.context = {
            "cluster_id": cluster.cluster_id,
            "root_cause": cluster.root_cause,
            "affected_files": cluster.affected_files,
            "finding_ids": cluster.finding_ids,
            "confidence": cluster.confidence,
            "estimated_impact": cluster.estimated_impact,
        }

    for cluster in campaign.escalations:
        child = await repo.create(
            intent=f"[ESCALATION] {cluster.proposed_fix}",
            assigned_role="Human",
            status="awaiting_approval",
        )
        child.parent_task_id = parent.id
        child.requires_approval = True
        child.context = {
            "cluster_id": cluster.cluster_id,
            "root_cause": cluster.root_cause,
            "constitutional_amendment_needed": cluster.proposed_fix,
            "affected_files": cluster.affected_files,
        }

    await session.commit()
    logger.info(
        "Campaign persisted: parent=%s, %d tasks, %d escalations",
        parent.id,
        campaign.autonomous_task_count,
        campaign.escalation_count,
    )


# ID: b63d2bae-56c3-4f98-80e3-f1c9cc170ca3
async def execute_autonomous_tasks(
    ctx: CoreContext, campaign: StrategicCampaign
) -> None:
    """Execute non-escalation clusters via develop_from_goal.

    Clusters below the 0.7 confidence threshold are skipped — they remain
    persisted as pending Tasks for a human to review rather than being
    autonomously executed.

    develop_from_goal owns its own WorkflowOrchestrator and does not accept a
    session; the caller's session governs persistence only (persist_campaign).
    """
    from will.autonomy.autonomous_developer import develop_from_goal

    logger.info("Executing %d autonomous tasks...", campaign.autonomous_task_count)

    for i, cluster in enumerate(campaign.clusters, 1):
        logger.info(
            "  [%d/%d] %s (impact=%s, confidence=%.2f)",
            i,
            campaign.autonomous_task_count,
            cluster.root_cause[:80],
            cluster.estimated_impact,
            cluster.confidence,
        )

        if cluster.confidence < 0.7:
            logger.info("    Skipping (confidence too low — staged for review)")
            continue

        success, message = await develop_from_goal(
            context=ctx,
            goal=cluster.proposed_fix,
            workflow_type=cluster.workflow_type,
            write=True,
        )
        logger.info("    %s %s", "OK" if success else "FAIL", message)
