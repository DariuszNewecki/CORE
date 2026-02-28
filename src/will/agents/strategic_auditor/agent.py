# src/will/agents/strategic_auditor/agent.py

"""
StrategicAuditor — CORE's self-awareness agent.

Reads full system state, reasons about it as a whole, produces a prioritised
remediation campaign, and executes what is constitutionally permitted.

Constitutional role:
- Reads everything (audit, DB, .intent/, git) — never writes to .intent/
- Flags anything requiring .intent/ amendment as escalation (requires_approval=True)
- Executes autonomous tasks via develop_from_goal
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from shared.infrastructure.repositories.task_repository import TaskRepository
from shared.logger import getLogger
from will.agents.strategic_auditor.context_gatherer import SystemContextGatherer
from will.agents.strategic_auditor.models import RootCauseCluster, StrategicCampaign
from will.agents.traced_agent_mixin import TracedAgentMixin
from will.orchestration.decision_tracer import DecisionTracer


if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from shared.context import CoreContext
    from will.orchestration.cognitive_service import CognitiveService


logger = getLogger(__name__)


_STRATEGIC_AUDIT_PROMPT = """
You are the strategic reasoning layer of CORE — a constitutional autonomous
development system. Your job is to reason about CORE's current state as a
whole and produce a prioritised remediation campaign.

IMPORTANT CONSTRAINTS:
- You can only suggest changes to files under src/ or tests/
- You CANNOT suggest changes to .intent/ files (the constitution)
- If a fix genuinely requires changing .intent/, set requires_constitution_change=true
  and explain what amendment is needed — a human will handle it
- Focus on ROOT CAUSES, not symptoms — one fix should eliminate many findings
- Order clusters by impact: fix the thing that unblocks the most other things first

--- SYSTEM STATE (6 DIMENSIONS) ---

DIMENSION 1 — CONSTITUTIONAL HEALTH ({finding_count} findings):
{audit_findings_summary}

DIMENSION 2 — SEMANTIC LANDSCAPE (what concepts is CORE built from?):
{semantic_landscape}

DIMENSION 3 — KNOWLEDGE GAPS (where is CORE blind to itself?):
{knowledge_gaps}

DIMENSION 4 — STRUCTURAL HEALTH (what does CORE contain?):
{structural_health}

DIMENSION 5 — CHANGE CONTEXT (what is CORE becoming?):
{change_context}

DIMENSION 6 — INTENT DRIFT (where does meaning diverge from code?):
{intent_drift}

CONSTITUTION:
{constitution_summary}

--- YOUR TASK ---

1. Identify ROOT CAUSE CLUSTERS: group findings that share the same underlying cause.
   Use ALL six dimensions — a violation cluster + semantic hotspot + drift signal
   together indicate a much deeper problem than any one signal alone.

2. For each cluster:
   - root_cause: one sentence, precise
   - affected_files: list of files
   - proposed_fix: concrete, actionable
   - requires_constitution_change: true only if .intent/ amendment is needed
   - confidence: 0.0-1.0
   - estimated_impact: low / medium / high

3. Write a SYSTEM SUMMARY: one paragraph assessing CORE's current health across
   all six dimensions.

4. Order clusters: highest impact first, constitutional amendments last.

Respond ONLY with valid JSON:
{{
  "system_summary": "...",
  "clusters": [
    {{
      "cluster_id": "cluster_001",
      "root_cause": "...",
      "affected_files": ["src/..."],
      "finding_ids": ["rule.id.1"],
      "proposed_fix": "...",
      "requires_constitution_change": false,
      "confidence": 0.9,
      "estimated_impact": "high"
    }}
  ]
}}
"""


# ID: sa-strategic-auditor
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

    # ID: sa-run
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
        logger.info("🧠 STRATEGIC AUDIT — CORE Self-Awareness Cycle")
        logger.info("=" * 70)

        gatherer = SystemContextGatherer(self._ctx, self._cognitive)
        system_context = await gatherer.gather(session)

        campaign = await self._reason(system_context)

        if write:
            await self._persist_campaign(session, campaign)

        if write and execute_autonomous:
            await self._execute_autonomous_tasks(session, campaign)

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

    # ID: sa-reason
    async def _reason(self, system_context: dict[str, Any]) -> StrategicCampaign:
        """Send system context to LLM and parse the strategic campaign."""
        import json as _json

        findings = system_context.get("audit_findings", [])

        # Compact findings by rule (avoid token overflow)
        findings_by_rule: dict[str, list[str]] = {}
        for f in findings:
            rid = f.get("rule_id", "unknown")
            ffile = f.get("file", "unknown")
            findings_by_rule.setdefault(rid, []).append(ffile)

        lines = []
        for rid, files in sorted(findings_by_rule.items()):
            unique = sorted(set(files))[:5]
            suffix = f" (+{len(files) - 5} more)" if len(files) > 5 else ""
            lines.append(
                f"  [{rid}] in {len(files)} locations: {', '.join(unique)}{suffix}"
            )

        def _compact(obj: Any, max_chars: int = 1500) -> str:
            s = _json.dumps(obj, indent=2, default=str)
            return s[:max_chars] + "..." if len(s) > max_chars else s

        prompt = _STRATEGIC_AUDIT_PROMPT.format(
            finding_count=len(findings),
            audit_findings_summary="\n".join(lines[:50]),
            semantic_landscape=_compact(system_context.get("semantic_landscape", {})),
            knowledge_gaps=_compact(system_context.get("knowledge_gaps", {})),
            structural_health=_compact(system_context.get("structural_health", {})),
            change_context=_compact(system_context.get("change_context", {})),
            intent_drift=_compact(system_context.get("intent_drift", {})),
            constitution_summary=_compact(
                {
                    "policy_count": system_context.get("constitution_summary", {}).get(
                        "policy_count", 0
                    ),
                    "policies": system_context.get("constitution_summary", {}).get(
                        "policy_ids", []
                    )[:15],
                }
            ),
        )

        logger.info("🤔 Reasoning about system state (LLM call)...")

        try:
            client = await self._cognitive.aget_client_for_role("Architect")
            response = await client.make_request_async(prompt)
            raw = response.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            data = json.loads(raw.strip())
        except Exception as e:
            logger.error("LLM reasoning failed: %s", e)
            data = {"system_summary": f"Strategic audit failed: {e}", "clusters": []}

        campaign_id = str(uuid.uuid4())
        clusters, escalations = [], []

        for c in data.get("clusters", []):
            cluster = RootCauseCluster(
                cluster_id=c.get("cluster_id", str(uuid.uuid4())[:8]),
                root_cause=c.get("root_cause", ""),
                affected_files=c.get("affected_files", []),
                finding_ids=c.get("finding_ids", []),
                proposed_fix=c.get("proposed_fix", ""),
                requires_constitution_change=c.get(
                    "requires_constitution_change", False
                ),
                confidence=float(c.get("confidence", 0.8)),
                estimated_impact=c.get("estimated_impact", "medium"),
            )
            (escalations if cluster.requires_constitution_change else clusters).append(
                cluster
            )

        return StrategicCampaign(
            campaign_id=campaign_id,
            created_at=datetime.now(UTC),
            system_summary=data.get("system_summary", ""),
            clusters=clusters,
            escalations=escalations,
            total_findings=len(findings),
            autonomous_task_count=len(clusters),
            escalation_count=len(escalations),
        )

    # ID: sa-persist
    async def _persist_campaign(
        self, session: AsyncSession, campaign: StrategicCampaign
    ) -> None:
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
            "✅ Campaign persisted: parent=%s, %d tasks, %d escalations",
            parent.id,
            campaign.autonomous_task_count,
            campaign.escalation_count,
        )

    # ID: sa-execute-autonomous
    async def _execute_autonomous_tasks(
        self, session: AsyncSession, campaign: StrategicCampaign
    ) -> None:
        """Execute non-escalation clusters via develop_from_goal."""
        from will.autonomy.autonomous_developer import (
            develop_from_goal,
            infer_workflow_type,
        )

        logger.info(
            "🚀 Executing %d autonomous tasks...", campaign.autonomous_task_count
        )

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
                logger.info(
                    "    ↳ ⏸️  Skipping (confidence too low — staged for review)"
                )
                continue

            workflow = infer_workflow_type(cluster.proposed_fix)
            success, message = await develop_from_goal(
                context=self._ctx,
                goal=cluster.proposed_fix,
                workflow_type=workflow,
                write=True,
                session=session,
            )
            logger.info("    ↳ %s %s", "✅" if success else "❌", message)

    # ID: sa-log-summary
    def _log_summary(self, campaign: StrategicCampaign) -> None:
        """Print human-readable campaign summary to console."""
        logger.info("")
        logger.info("=" * 70)
        logger.info("📊 STRATEGIC AUDIT RESULTS")
        logger.info("=" * 70)
        logger.info("")
        logger.info("SYSTEM ASSESSMENT:")
        logger.info("%s", campaign.system_summary)
        logger.info("")
        logger.info(
            "FINDINGS: %d total → %d root cause clusters → %d escalations",
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
                "⚠️  ESCALATIONS (require your review — .intent/ amendment needed):"
            )
            for i, c in enumerate(campaign.escalations, 1):
                logger.info("  %d. %s", i, c.root_cause)
                logger.info("     Amendment needed: %s", c.proposed_fix[:120])

        logger.info("")
        logger.info("Campaign ID: %s", campaign.campaign_id)
        logger.info("=" * 70)

    # ID: sa-format-machine
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
