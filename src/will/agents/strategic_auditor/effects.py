# src/will/agents/strategic_auditor/effects.py

"""
StrategicAuditor — campaign side effects on the world.

Two operations, both taking a finished StrategicCampaign or its persisted
parent and both governed by the per-cluster governor review surface
(ADR-110 D4 — self-extension is a Governor-role capability):

- persist_campaign: write a parent Task plus one child Task per autonomous
  cluster (status='pending', requires_approval=True — nothing runs until the
  governor clears requires_approval) and one escalation Task per
  amendment-required cluster (status='blocked'), via TaskRepository. Returns
  the parent Task id (the review handle).
- execute_approved_clusters: load a campaign's child Tasks, run only the
  autonomous ones the governor has cleared (status='pending',
  requires_approval=False) via develop_from_goal. There is no blanket
  confidence gate — the governor's per-cluster acceptance is the gate.

Approval is carried by the Task.requires_approval flag (its purpose), kept
orthogonal to the status lifecycle, which stays within core.tasks'
closed-vocab CHECK (pending/planning/executing/validating/completed/failed/
blocked). A rejected cluster is moved to 'blocked'.

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
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from shared.context import CoreContext


logger = getLogger(__name__)


# ID: f4d82377-ffce-4794-9bc3-754a48eed83d
async def persist_campaign(session: AsyncSession, campaign: StrategicCampaign) -> UUID:
    """Store campaign as parent Task + child Tasks; return the parent Task id.

    Autonomous clusters persist as ``awaiting_approval`` / ``requires_approval``
    — nothing executes until the governor accepts the cluster through the review
    surface (ADR-110 D4). The returned parent id is the review handle.
    """
    repo = TaskRepository(session)

    parent = await repo.create(
        intent=f"[StrategicCampaign:{campaign.campaign_id}] {campaign.system_summary[:200]}",
        assigned_role="StrategicAuditor",
        status="planning",
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
        child.requires_approval = True
        child.context = {
            "cluster_id": cluster.cluster_id,
            "root_cause": cluster.root_cause,
            "affected_files": cluster.affected_files,
            "finding_ids": cluster.finding_ids,
            "confidence": cluster.confidence,
            "estimated_impact": cluster.estimated_impact,
            "workflow_type": cluster.workflow_type,
        }

    for cluster in campaign.escalations:
        child = await repo.create(
            intent=f"[ESCALATION] {cluster.proposed_fix}",
            assigned_role="Human",
            status="blocked",
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
        "Campaign persisted (awaiting per-cluster review): parent=%s, %d clusters, %d escalations",
        parent.id,
        campaign.autonomous_task_count,
        campaign.escalation_count,
    )
    return parent.id


# ID: b63d2bae-56c3-4f98-80e3-f1c9cc170ca3
async def execute_approved_clusters(
    ctx: CoreContext, session: AsyncSession, parent_task_id: UUID
) -> list[tuple[str, bool, str]]:
    """Execute the governor-approved autonomous clusters of one campaign.

    Only autonomous child Tasks the governor has cleared run — ``status='pending'``
    with ``requires_approval=False``. The governor's per-cluster acceptance
    (clearing requires_approval) is the gate; there is no blanket confidence
    floor. Each executed cluster's Task is moved to ``completed`` or ``failed``.

    develop_from_goal owns its own WorkflowOrchestrator and does not accept a
    session; the caller's session governs persistence only.

    Returns a (cluster_task_id, ok, message) tuple per executed cluster.
    """
    from will.autonomy.autonomous_developer import develop_from_goal

    repo = TaskRepository(session)
    children = await repo.list_children(parent_task_id)
    approved = [
        c
        for c in children
        if c.assigned_role == "AutonomousDeveloper"
        and c.status == "pending"
        and not c.requires_approval
    ]

    logger.info(
        "Executing %d approved cluster(s) of campaign parent=%s",
        len(approved),
        parent_task_id,
    )

    results: list[tuple[str, bool, str]] = []
    for child in approved:
        workflow_type = (child.context or {}).get(
            "workflow_type", "full_feature_development"
        )
        success, message = await develop_from_goal(
            context=ctx,
            goal=child.intent,
            workflow_type=workflow_type,
            write=True,
        )
        await repo.update_status(child.id, "completed" if success else "failed")
        logger.info("    %s %s", "OK" if success else "FAIL", message)
        results.append((str(child.id), success, message))

    return results
