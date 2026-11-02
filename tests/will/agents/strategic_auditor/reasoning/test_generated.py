from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

from will.agents.strategic_auditor.reasoning import synthesize_campaign


# ID: 342ce458-d0a7-463a-a7d8-309775797a24
def test_synthesize_campaign():
    system_context = {
        "audit_findings": [
            {"check_id": "rule_a", "file_path": "a.py"},
            {"check_id": "rule_a", "file_path": "b.py"},
            {"rule_id": "rule_b", "file": "c.py"},
        ],
        "structural_health": {"score": 0.9},
    }

    llm_response = json.dumps(
        {
            "system_summary": "all good",
            "clusters": [
                {
                    "cluster_id": "c1",
                    "root_cause": "cause1",
                    "affected_files": ["a.py"],
                    "finding_ids": ["f1"],
                    "proposed_fix": "fix1",
                    "requires_constitution_change": False,
                    "confidence": 0.9,
                    "estimated_impact": "high",
                    "workflow_type": "standard",
                },
                {
                    "cluster_id": "c2",
                    "root_cause": "cause2",
                    "affected_files": ["c.py"],
                    "finding_ids": ["f2"],
                    "proposed_fix": "fix2",
                    "requires_constitution_change": True,
                    "confidence": 0.7,
                    "estimated_impact": "medium",
                    "workflow_type": "constitution",
                },
            ],
        }
    )

    mock_model = MagicMock()
    mock_model.manifest = MagicMock(role="strategic_auditor")
    mock_model.invoke = AsyncMock(return_value=llm_response)

    cognitive = MagicMock()
    cognitive.aget_client_for_role = AsyncMock(return_value=MagicMock())

    with (
        patch(
            "will.agents.strategic_auditor.reasoning.PromptModel"
        ) as mock_prompt_model,
        patch(
            "will.agents.strategic_auditor.reasoning._resolve_workflow_type",
            side_effect=lambda x: x,
        ),
    ):
        mock_prompt_model.load.return_value = mock_model

        result = __import__("asyncio").run(
            synthesize_campaign(cognitive, system_context)
        )

    assert result.total_findings == 3
    assert result.system_summary == "all good"
    assert len(result.clusters) == 1
    assert len(result.escalations) == 1
    assert result.clusters[0].cluster_id == "c1"
    assert result.escalations[0].cluster_id == "c2"
    assert result.autonomous_task_count == 1
    assert result.escalation_count == 1
    mock_model.invoke.assert_awaited_once()
    cognitive.aget_client_for_role.assert_awaited_once_with("strategic_auditor")
