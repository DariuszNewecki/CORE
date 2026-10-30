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


import pytest


@pytest.mark.asyncio
# ID: c1575155-83ea-42f0-822f-6fa82feb4a9b
async def test_post_reconnaissance_records():
    from will.orchestration.goal_run_records import post_reconnaissance_records

    poster = MagicMock()
    poster.post_unavailable = AsyncMock()
    poster.post_report = AsyncMock()

    plan_data = {
        "reconnaissance": {
            "available": True,
            "digest": "digest-abc",
            "raw": {"files": ["a.py"]},
            "view": {"path": "/repo", "excludes": []},
            "unavailable": [
                {"topic": "migrations", "reason": "no_sql_files"},
                "not-a-dict",
            ],
        }
    }

    with patch(
        "will.orchestration.goal_run_records.blackboard_safe",
        side_effect=lambda x: x,
    ):
        await post_reconnaissance_records(poster, "run-1", plan_data)

    poster.post_unavailable.assert_not_awaited()

    report_calls = poster.post_report.await_args_list
    assert len(report_calls) == 2

    first_args = report_calls[0].args
    assert first_args[0] == "goal_run.run-1.recon"
    assert first_args[1]["run_id"] == "run-1"
    assert first_args[1]["digest"] == "digest-abc"
    assert first_args[1]["observed"] == {"files": ["a.py"]}
    assert first_args[1]["view"] == {"path": "/repo", "excludes": []}

    second_args = report_calls[1].args
    assert second_args[0].startswith("goal_run.run-1.unavailable.")
    assert second_args[1]["run_id"] == "run-1"
    assert second_args[1]["topic"] == "migrations"
    assert second_args[1]["reason"] == "no_sql_files"


import dataclasses
from typing import Any

from pydantic import BaseModel

from will.orchestration.goal_run_records import blackboard_safe


class _Task(BaseModel):
    name: str
    count: int


@dataclasses.dataclass
class _Step:
    label: str
    weight: float


class _Op(BaseModel):
    id: int


# ID: 6987c772-57c4-4d88-bcc9-eb1d3cbea484
def test_blackboard_safe() -> None:
    value: Any = {
        "execution_plan": [_Task(name="build", count=2), _Task(name="ship", count=1)],
        "steps": (_Step(label="scan", weight=0.5),),
        "plain": 42,
        "nested": {"plan": [_Op(id=7)]},
    }

    result = blackboard_safe(value)

    assert result == {
        "execution_plan": [
            {"name": "build", "count": 2},
            {"name": "ship", "count": 1},
        ],
        "steps": [{"label": "scan", "weight": 0.5}],
        "plain": 42,
        "nested": {"plan": [{"id": 7}]},
    }
    # Containers are normalised to lists and all models/dataclasses are gone.
    assert isinstance(result["steps"], list)
    assert not any(isinstance(v, BaseModel) for v in result["execution_plan"])
