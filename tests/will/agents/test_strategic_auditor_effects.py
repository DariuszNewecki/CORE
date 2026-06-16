"""StrategicAuditor effects — autonomous execution call contract.

Regression guard for the #115 gap-analysis finding: execute_autonomous_tasks
dispatched to develop_from_goal with a session= kwarg that develop_from_goal
does not accept, so the --execute path raised TypeError on the first cluster
>= 0.7 confidence. These tests autospec develop_from_goal so the mock enforces
its real signature — a session= kwarg (or any other arity drift) fails the
call exactly as it would at runtime.

The tests assert the dispatch contract only; no LLM, DB, or orchestrator path
is exercised.
"""

from __future__ import annotations

from unittest.mock import MagicMock, create_autospec

import pytest

# body.atomic must finish loading before will.agents pulls in
# will.autonomy.proposal — pre-existing body.atomic <-> will.autonomy circular
# import surfaces during isolated collection otherwise.
import body.atomic  # noqa: F401  -- import-order side effect, not a usage
import will.autonomy.autonomous_developer as autonomous_developer
from will.agents.strategic_auditor.effects import execute_autonomous_tasks
from will.agents.strategic_auditor.models import RootCauseCluster, StrategicCampaign


def _campaign(*clusters: RootCauseCluster) -> StrategicCampaign:
    return StrategicCampaign(
        campaign_id="test-campaign",
        created_at=__import__("datetime").datetime(2026, 6, 16),
        system_summary="test",
        clusters=list(clusters),
        autonomous_task_count=len(clusters),
    )


def _cluster(confidence: float) -> RootCauseCluster:
    return RootCauseCluster(
        cluster_id="c1",
        root_cause="root",
        affected_files=["a.py"],
        finding_ids=["f1"],
        proposed_fix="do the thing",
        confidence=confidence,
    )


@pytest.mark.asyncio
# ID: 6f8d2b1a-4c3e-4a7f-9b2d-1e5c8a0f3d27
async def test_execute_dispatches_with_valid_develop_from_goal_signature(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A >=0.7 cluster dispatches to develop_from_goal without a session kwarg.

    autospec enforces the real signature; passing session= (the old bug) would
    raise TypeError here, exactly as it did at runtime.
    """
    mock_dfg = create_autospec(
        autonomous_developer.develop_from_goal, return_value=(True, "ok")
    )
    monkeypatch.setattr(autonomous_developer, "develop_from_goal", mock_dfg)

    await execute_autonomous_tasks(MagicMock(name="CoreContext"), _campaign(_cluster(0.8)))

    mock_dfg.assert_awaited_once()
    _, kwargs = mock_dfg.await_args
    assert "session" not in kwargs
    assert kwargs["write"] is True
    assert kwargs["workflow_type"] == "full_feature_development"


@pytest.mark.asyncio
# ID: b2a7e914-8d6c-4f01-a3b5-7c9e2d4f6018
async def test_execute_skips_low_confidence_cluster(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Clusters below the 0.7 confidence floor are not dispatched."""
    mock_dfg = create_autospec(
        autonomous_developer.develop_from_goal, return_value=(True, "ok")
    )
    monkeypatch.setattr(autonomous_developer, "develop_from_goal", mock_dfg)

    await execute_autonomous_tasks(MagicMock(name="CoreContext"), _campaign(_cluster(0.5)))

    mock_dfg.assert_not_awaited()
