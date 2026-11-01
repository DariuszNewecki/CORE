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
