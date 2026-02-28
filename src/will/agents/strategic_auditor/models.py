# src/will/agents/strategic_auditor/models.py

"""
Data structures for the StrategicAuditor campaign.

Pure data — no logic, no imports from CORE internals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


# ID: sa-root-cause-cluster
@dataclass
# ID: 2ebdd1a6-3c94-4b49-8d61-00f8ed2ba976
class RootCauseCluster:
    """
    A group of audit findings that share a single root cause.

    The LLM produces these — they are the core reasoning unit of the campaign.
    """

    cluster_id: str
    root_cause: str
    """Single sentence: why do all these findings exist?"""

    affected_files: list[str]
    finding_ids: list[str]
    proposed_fix: str
    """Concrete, actionable description of what needs to change."""

    requires_constitution_change: bool = False
    """True → escalate to human. False → CORE can fix autonomously."""

    confidence: float = 0.8
    estimated_impact: str = "medium"
    """low / medium / high — how much does fixing this improve CORE?"""


# ID: sa-campaign
@dataclass
# ID: 75de5708-f567-46e4-a350-bfadc21c6e19
class StrategicCampaign:
    """
    The full output of a StrategicAuditor run.

    Stored as a parent Task in PostgreSQL with child Tasks per cluster.
    """

    campaign_id: str
    created_at: datetime
    system_summary: str
    """LLM's one-paragraph assessment of CORE's current state."""

    clusters: list[RootCauseCluster] = field(default_factory=list)
    escalations: list[RootCauseCluster] = field(default_factory=list)
    """Clusters that require human (.intent/) amendment."""

    total_findings: int = 0
    autonomous_task_count: int = 0
    escalation_count: int = 0
