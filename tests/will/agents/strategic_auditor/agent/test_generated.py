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
