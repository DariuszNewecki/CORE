from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock


# ID: 76cfb528-1503-442b-8ba8-c53e88f44225
async def test_PromptDriftSensor_run() -> None:
    from will.workers.prompt_drift_sensor import PromptDriftSensor

    sensor = PromptDriftSensor()

    sensor.post_heartbeat = AsyncMock()
    sensor.post_finding = AsyncMock()
    sensor.post_report = AsyncMock()

    governed = [
        {"name": "prompt_a", "anchors": ["ADR-001"]},
        {"name": "prompt_b", "anchors": ["ADR-002"]},
    ]
    sensor._load_governed_prompts = MagicMock(return_value=governed)
    sensor._get_current_commit = MagicMock(return_value="abc123")

    def _compute_hashes(name: str):
        if name == "prompt_a":
            return "hash_a_new", {"f1": "h1"}
        return "hash_b", {"f2": "h2"}

    sensor._compute_hashes = MagicMock(side_effect=_compute_hashes)

    baseline = {
        "hashes": {"prompt_a": "hash_a_old", "prompt_b": "hash_b"},
        "file_hashes": {"prompt_a": {"f1": "h1_old"}, "prompt_b": {"f2": "h2"}},
    }
    sensor._fetch_baseline = AsyncMock(return_value=baseline)

    await sensor.run()

    sensor.post_heartbeat.assert_awaited_once()

    sensor.post_finding.assert_awaited_once()
    finding_kwargs = sensor.post_finding.await_args.kwargs
    assert finding_kwargs["subject"] == "prompt::drift::prompt_a"
    assert finding_kwargs["payload"]["prompt_name"] == "prompt_a"
    assert finding_kwargs["payload"]["previous_hash"] == "hash_a_old"
    assert finding_kwargs["payload"]["current_hash"] == "hash_a_new"
    assert finding_kwargs["payload"]["git_commit"] == "abc123"

    sensor.post_report.assert_awaited_once()
    report_kwargs = sensor.post_report.await_args.kwargs
    assert report_kwargs["subject"] == "prompt_drift_sensor.baseline"
    assert report_kwargs["payload"]["hashes"] == {
        "prompt_a": "hash_a_new",
        "prompt_b": "hash_b",
    }
    assert report_kwargs["payload"]["checked"] == 2
    assert report_kwargs["payload"]["drifted"] == ["prompt_a"]



import pytest


@pytest.mark.asyncio
# ID: a71c29e4-afb7-46d8-957b-3def3d7814c3
async def test_PromptDriftSensor():
    from will.workers.prompt_drift_sensor import PromptDriftSensor

    worker = PromptDriftSensor()
    worker.post_heartbeat = AsyncMock()
    worker.post_finding = AsyncMock()
    worker.post_report = AsyncMock()

    worker._load_governed_prompts = MagicMock(return_value=[])
    worker._fetch_baseline = AsyncMock(return_value=None)

    await worker.run()

    worker.post_heartbeat.assert_awaited_once()
    worker.post_report.assert_awaited_once()
    kwargs = worker.post_report.call_args.kwargs
    assert kwargs["subject"] == "prompt_drift_sensor.baseline"
    assert kwargs["payload"]["checked"] == 0
    assert kwargs["payload"]["drifted"] == []
