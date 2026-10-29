from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from will.orchestration.goal_run_records import post_finding_records


# ID: 79985837-fe12-42ed-90a8-652811eabdfd
async def test_post_finding_records() -> None:
    runtime_phase = MagicMock()
    runtime_phase.name = "runtime"
    runtime_phase.data = {
        "investigation": {
            "findings": [
                {"summary": "found a", "detail": "x"},
                {"summary": "found b", "detail": "y"},
            ],
            "steps_executed": 3,
        }
    }

    result = MagicMock()
    result.phase_results = [runtime_phase]

    poster = MagicMock()
    poster.post_report = AsyncMock()

    await post_finding_records(poster, "run-123", result)

    assert poster.post_report.await_count == 2
    first_call = poster.post_report.await_args_list[0]
    assert first_call.args[0] == "goal_run.run-123.finding.1"
    assert first_call.args[1]["run_id"] == "run-123"
    assert first_call.args[1]["index"] == 1


from unittest.mock import patch

import pytest

from will.orchestration.goal_run_records import post_decision_records


@pytest.mark.asyncio
# ID: 95201e7e-bc91-4008-87b3-9cf59295d17d
async def test_post_decision_records():
    poster = AsyncMock()
    poster.post_report = AsyncMock()

    plan_data = {
        "decisions": [
            {
                "rationale": "best choice",
                "action": "do_a",
                "alternatives": ["do_b"],
                "confidence": 0.9,
            },
            {
                "rationale": "second",
                "action": "do_c",
                "alternatives": [],
                "confidence": 0.5,
            },
        ]
    }

    with patch(
        "will.orchestration.goal_run_records.blackboard_safe",
        side_effect=lambda d: dict(d),
    ):
        await post_decision_records(poster, "run-42", plan_data)

    assert poster.post_report.await_count == 2

    first_call = poster.post_report.await_args_list[0]
    assert first_call.args[0] == "goal_run.run-42.decision.1"
    first_payload = first_call.args[1]
    assert first_payload["run_id"] == "run-42"
    assert first_payload["index"] == 1
    assert first_payload["action"] == "do_a"
    assert first_payload["confidence"] == 0.9

    second_call = poster.post_report.await_args_list[1]
    assert second_call.args[0] == "goal_run.run-42.decision.2"
    second_payload = second_call.args[1]
    assert second_payload["run_id"] == "run-42"
    assert second_payload["index"] == 2
    assert second_payload["action"] == "do_c"
