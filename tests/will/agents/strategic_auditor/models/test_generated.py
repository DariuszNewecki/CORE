from __future__ import annotations

from datetime import UTC, datetime

from will.agents.strategic_auditor.models import StrategicCampaign


# ID: 39dea8f9-219d-4bb0-ac62-47930ba6a996
def test_StrategicCampaign():
    created_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)

    campaign = StrategicCampaign(
        campaign_id="campaign-123",
        created_at=created_at,
        system_summary="CORE is in a stable state.",
    )

    assert campaign.campaign_id == "campaign-123"
    assert campaign.created_at == created_at
    assert campaign.system_summary == "CORE is in a stable state."
    assert campaign.clusters == []
    assert campaign.escalations == []
    assert campaign.total_findings == 0
    assert campaign.autonomous_task_count == 0
    assert campaign.escalation_count == 0
    assert campaign.parent_task_id is None


from will.agents.strategic_auditor.models import RootCauseCluster


# ID: a1549d4e-5d29-4c19-8cf6-76e43e30c26f
def test_RootCauseCluster():
    cluster = RootCauseCluster(
        cluster_id="cluster-001",
        root_cause="Duplicate validation logic across services causes drift.",
        affected_files=["src/a.py", "src/b.py"],
        finding_ids=["f1", "f2"],
        proposed_fix="Extract shared validator into core.validation module.",
    )

    assert cluster.cluster_id == "cluster-001"
    assert (
        cluster.root_cause == "Duplicate validation logic across services causes drift."
    )
    assert cluster.affected_files == ["src/a.py", "src/b.py"]
    assert cluster.finding_ids == ["f1", "f2"]
    assert (
        cluster.proposed_fix == "Extract shared validator into core.validation module."
    )

    # Defaults
    assert cluster.requires_constitution_change is False
    assert cluster.confidence == 0.8
    assert cluster.estimated_impact == "medium"
    assert cluster.workflow_type == "full_feature_development"
