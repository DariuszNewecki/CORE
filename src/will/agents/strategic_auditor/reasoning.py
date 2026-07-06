# src/will/agents/strategic_auditor/reasoning.py

"""
StrategicAuditor — campaign synthesis.

The LLM contract layer for StrategicAuditor. Takes a system_context dict
gathered by SystemContextGatherer and produces a StrategicCampaign by:

1. Compacting findings into a per-rule summary (token-budget aware).
2. Invoking the architect_threats_analysis_prompt PromptModel.
3. Parsing the JSON response (fenced-block tolerant).
4. Constructing RootCauseCluster instances and partitioning them into
   autonomous-vs-escalation buckets per requires_constitution_change.

Fail-soft: on any LLM/parse error the function returns a campaign with an
empty cluster list and a diagnostic system_summary so the caller's
downstream effects (persist, execute, log) still have something coherent
to operate on.

LAYER: will/agents — collaborator of StrategicAuditor. No DB writes, no
file writes, no .intent/ access. The only side effect is the LLM call.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from shared.ai.prompt_model import PromptModel
from shared.infrastructure.intent.operational_config import load_operational_config
from shared.logger import getLogger
from will.agents.strategic_auditor.models import RootCauseCluster, StrategicCampaign


if TYPE_CHECKING:
    from will.orchestration.cognitive_service import CognitiveService


logger = getLogger(__name__)

_CFG_SA = load_operational_config().strategic_auditor

_VALID_WORKFLOW_TYPES = frozenset(
    {
        "refactor_modularity",
        "coverage_remediation",
        "code_modification",
    }
)


def _resolve_workflow_type(value: str) -> str:
    """Return value if it is a known workflow type, else the safe default."""
    if isinstance(value, str) and value.strip() in _VALID_WORKFLOW_TYPES:
        return value.strip()
    logger.warning(
        "Unknown or missing workflow_type '%s' from LLM — "
        "defaulting to code_modification",
        value,
    )
    return "code_modification"


# ID: b1f24560-023b-4482-819a-169708c7130f
async def synthesize_campaign(
    cognitive: CognitiveService,
    system_context: dict[str, Any],
) -> StrategicCampaign:
    """Send system context to the LLM and parse the strategic campaign.

    The prompt name (architect_threats_analysis_prompt) and the expected
    response schema (clusters list with root_cause / proposed_fix /
    requires_constitution_change / workflow_type / confidence / impact)
    are the LLM contract this function owns.
    """
    findings = system_context.get("audit_findings", [])

    findings_by_rule: dict[str, list[str]] = {}
    for f in findings:
        # as_dict() uses "check_id"/"file_path"; the fallback branch in
        # context_gatherer uses "rule_id"/"file" — accept both.
        rid = f.get("rule_id") or f.get("check_id") or "unknown"
        ffile = f.get("file_path") or f.get("file") or "unknown"
        findings_by_rule.setdefault(rid, []).append(ffile)

    lines = []
    for rid, files in sorted(findings_by_rule.items()):
        unique = sorted(set(files))[:5]
        suffix = f" (+{len(files) - 5} more)" if len(files) > 5 else ""
        lines.append(
            f"  [{rid}] in {len(files)} locations: {', '.join(unique)}{suffix}"
        )

    def _compact(obj: Any, max_chars: int = _CFG_SA.compact_max_chars) -> str:
        s = json.dumps(obj, indent=2, default=str)
        return s[:max_chars] + "..." if len(s) > max_chars else s

    logger.info("Reasoning about system state (LLM call)...")

    try:
        model = PromptModel.load("architect_threats_analysis_prompt")
        client = await cognitive.aget_client_for_role(model.manifest.role)
        response = await model.invoke(
            context={
                "finding_count": len(findings),
                "audit_findings_summary": "\n".join(lines[:50]),
                "semantic_landscape": _compact(
                    system_context.get("semantic_landscape", {})
                ),
                "knowledge_gaps": _compact(system_context.get("knowledge_gaps", {})),
                "structural_health": _compact(
                    system_context.get("structural_health", {})
                ),
                "change_context": _compact(system_context.get("change_context", {})),
                "intent_drift": _compact(system_context.get("intent_drift", {})),
                "constitution_summary": _compact(
                    {
                        "policy_count": system_context.get(
                            "constitution_summary", {}
                        ).get("policy_count", 0),
                        "policies": system_context.get("constitution_summary", {}).get(
                            "policy_ids", []
                        )[:15],
                    }
                ),
            },
            client=client,
            user_id="StrategicAuditor",
        )
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
    clusters: list[RootCauseCluster] = []
    escalations: list[RootCauseCluster] = []

    for c in data.get("clusters", []):
        cluster = RootCauseCluster(
            cluster_id=c.get("cluster_id", str(uuid.uuid4())[:8]),
            root_cause=c.get("root_cause", ""),
            affected_files=c.get("affected_files", []),
            finding_ids=c.get("finding_ids", []),
            proposed_fix=c.get("proposed_fix", ""),
            requires_constitution_change=c.get("requires_constitution_change", False),
            confidence=float(c.get("confidence", 0.8)),
            estimated_impact=c.get("estimated_impact", "medium"),
            workflow_type=_resolve_workflow_type(c.get("workflow_type", "")),
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
