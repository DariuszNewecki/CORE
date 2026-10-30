from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from will.agents.strategic_auditor.agent import StrategicAuditor


# ID: 020e1593-ba6f-410a-9249-1d12aa658752
def test_StrategicAuditor_format_machine():
    context = MagicMock()
    cognitive_service = MagicMock()

    with patch("will.agents.strategic_auditor.agent.DecisionTracer") as mock_tracer_cls:
        mock_tracer_cls.return_value = MagicMock()
        auditor = StrategicAuditor(context, cognitive_service)

    cluster = SimpleNamespace(
        cluster_id="cluster-1",
        root_cause="null pointer",
        proposed_fix="add guard",
        affected_files=["a.py", "b.py"],
        finding_ids=["f1", "f2"],
        confidence=0.9,
        estimated_impact="high",
        workflow_type="autonomous",
    )
    escalation = SimpleNamespace(
        cluster_id="cluster-2",
        root_cause="ambiguous spec",
        proposed_fix="amend charter",
        affected_files=["c.py"],
        confidence=0.5,
    )
    campaign = SimpleNamespace(
        campaign_id="camp-42",
        created_at=datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC),
        system_summary="overall healthy",
        total_findings=7,
        autonomous_task_count=3,
        escalation_count=1,
        clusters=[cluster],
        escalations=[escalation],
    )

    result = auditor.format_machine(campaign)

    assert result["campaign_id"] == "camp-42"
    assert result["created_at"] == "2024-01-02T03:04:05+00:00"
    assert result["system_summary"] == "overall healthy"
    assert result["stats"] == {
        "total_findings": 7,
        "autonomous_tasks": 3,
        "escalations": 1,
    }
    assert result["autonomous_clusters"] == [
        {
            "cluster_id": "cluster-1",
            "root_cause": "null pointer",
            "proposed_fix": "add guard",
            "affected_files": ["a.py", "b.py"],
            "finding_ids": ["f1", "f2"],
            "confidence": 0.9,
            "estimated_impact": "high",
            "workflow_type": "autonomous",
        }
    ]
    assert result["escalations"] == [
        {
            "cluster_id": "cluster-2",
            "root_cause": "ambiguous spec",
            "constitutional_amendment_needed": "amend charter",
            "affected_files": ["c.py"],
            "confidence": 0.5,
        }
    ]


from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
# ID: 44f00524-0a79-4888-8fba-5a0d439063ed
async def test_StrategicAuditor_run():
    context = MagicMock()
    cognitive_service = MagicMock()

    with patch("will.agents.strategic_auditor.agent.DecisionTracer") as mock_tracer_cls:
        mock_tracer = MagicMock()
        mock_tracer_cls.return_value = mock_tracer
        auditor = StrategicAuditor(context, cognitive_service)

    session = MagicMock()

    system_context = MagicMock()
    campaign = MagicMock()
    campaign.clusters = [MagicMock(), MagicMock()]
    campaign.escalations = [MagicMock()]
    campaign.total_findings = 7
    campaign.autonomous_task_count = 2
    campaign.escalation_count = 1
    campaign.campaign_id = "campaign-123"

    mock_gather = AsyncMock(return_value=system_context)
    mock_synthesize = AsyncMock(return_value=campaign)
    mock_persist = AsyncMock(return_value=42)
    mock_log_summary = MagicMock()

    mock_gatherer_instance = MagicMock()
    mock_gatherer_instance.gather = mock_gather

    with (
        patch(
            "will.agents.strategic_auditor.agent.SystemContextGatherer",
            return_value=mock_gatherer_instance,
        ),
        patch(
            "will.agents.strategic_auditor.agent.synthesize_campaign",
            mock_synthesize,
        ),
        patch(
            "will.agents.strategic_auditor.agent.persist_campaign",
            mock_persist,
        ),
        patch.object(auditor, "_log_summary", mock_log_summary),
    ):
        result = await auditor.run(session, write=True, execute_autonomous=False)

    assert result is campaign
    mock_gather.assert_awaited_once_with(session)
    mock_synthesize.assert_awaited_once_with(cognitive_service, system_context)
    mock_persist.assert_awaited_once_with(session, campaign)
    assert campaign.parent_task_id == "42"
    mock_log_summary.assert_called_once_with(campaign)
    mock_tracer.record.assert_called_once()
