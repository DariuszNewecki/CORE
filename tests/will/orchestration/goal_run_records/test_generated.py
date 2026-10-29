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
