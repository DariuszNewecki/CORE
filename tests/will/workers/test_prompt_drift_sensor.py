"""Tests for PromptDriftSensor (ADR-134 D6).

Verifies:
- _compute_hash returns a stable SHA-256 digest for a prompt directory
- _compute_hash returns None for a missing prompt directory
- run() posts a baseline report and no findings on the first cycle (no prior baseline)
- run() posts a drift finding when system.txt changes between cycles
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_sensor(tmp_prompts: Path) -> Any:
    """Instantiate PromptDriftSensor with Worker infrastructure mocked out."""
    from will.workers.prompt_drift_sensor import PromptDriftSensor

    decl: dict[str, Any] = {
        "kind": "worker",
        "metadata": {"id": "workers.prompt_drift_sensor", "title": "Prompt Drift Sensor"},
        "identity": {"uuid": str(uuid.uuid4()), "class": "sensing"},
        "mandate": {
            "phase": "audit",
            "approval_required": False,
            "scope": {"rule_namespace": "prompt.drift", "artifact_type": ["prompt"]},
            "schedule": {"max_interval": 900},
        },
        "implementation": {
            "module": "will.workers.prompt_drift_sensor",
            "class": "PromptDriftSensor",
            "requires_core_context": False,
        },
    }

    with (
        patch.object(PromptDriftSensor, "_load_declaration", return_value=decl),
        patch("shared.workers.blackboard_publisher.BlackboardPublisher.__init__", return_value=None),
    ):
        sensor = PromptDriftSensor.__new__(PromptDriftSensor)
        sensor._declaration = decl
        sensor._worker_uuid = uuid.uuid4()
        sensor._worker_name = "Prompt Drift Sensor"
        sensor._worker_class = "sensing"
        sensor._phase = "audit"
        sensor._approval_required = False
        sensor._max_interval = 900
        sensor._core_context = None

    publisher = MagicMock()
    publisher.post_heartbeat = AsyncMock(return_value=uuid.uuid4())
    publisher.post_report = AsyncMock(return_value=uuid.uuid4())
    publisher.post_finding = AsyncMock(return_value=uuid.uuid4())
    sensor._blackboard = publisher

    return sensor, publisher, tmp_prompts


def _write_prompt(prompts_root: Path, name: str, system_txt: str) -> None:
    d = prompts_root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "system.txt").write_text(system_txt)


def test_compute_hash_stable(tmp_path: Path) -> None:
    """_compute_hash returns the same digest on two calls with identical content."""
    prompts_root = tmp_path / "prompts"
    _write_prompt(prompts_root, "test_prompt", "You are a coder.")

    sensor, _, _ = _make_sensor(prompts_root)

    with patch("shared.infrastructure.settings.settings") as mock_settings:
        mock_settings.paths.prompts_dir = prompts_root
        h1 = sensor._compute_hash("test_prompt")
        h2 = sensor._compute_hash("test_prompt")

    assert h1 is not None
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex digest


def test_compute_hash_changes_on_content_change(tmp_path: Path) -> None:
    """_compute_hash produces a different digest after system.txt changes."""
    prompts_root = tmp_path / "prompts"
    _write_prompt(prompts_root, "test_prompt", "Version 1.")

    sensor, _, _ = _make_sensor(prompts_root)

    with patch("shared.infrastructure.settings.settings") as mock_settings:
        mock_settings.paths.prompts_dir = prompts_root
        h1 = sensor._compute_hash("test_prompt")
        (prompts_root / "test_prompt" / "system.txt").write_text("Version 2.")
        h2 = sensor._compute_hash("test_prompt")

    assert h1 != h2


def test_compute_hash_returns_none_for_missing_dir(tmp_path: Path) -> None:
    """_compute_hash returns None when the prompt directory does not exist."""
    prompts_root = tmp_path / "prompts"
    prompts_root.mkdir()

    sensor, _, _ = _make_sensor(prompts_root)

    with patch("shared.infrastructure.settings.settings") as mock_settings:
        mock_settings.paths.prompts_dir = prompts_root
        result = sensor._compute_hash("nonexistent_prompt")

    assert result is None


@pytest.mark.asyncio
async def test_run_first_cycle_no_findings(tmp_path: Path) -> None:
    """On the first cycle (no baseline), run() posts a report and no findings."""
    prompts_root = tmp_path / "prompts"
    _write_prompt(prompts_root, "my_prompt", "System content.")

    sensor, publisher, _ = _make_sensor(prompts_root)

    governed = [{"name": "my_prompt", "anchors": ["ADR-134"]}]

    with (
        patch.object(sensor, "_load_governed_prompts", return_value=governed),
        patch.object(sensor, "_fetch_baseline", new_callable=AsyncMock, return_value=None),
        patch("shared.infrastructure.settings.settings") as mock_settings,
    ):
        mock_settings.paths.prompts_dir = prompts_root
        await sensor.run()

    publisher.post_heartbeat.assert_called_once()
    publisher.post_report.assert_called_once()
    publisher.post_finding.assert_not_called()

    report_kwargs = publisher.post_report.call_args
    payload = report_kwargs[1]["payload"] if report_kwargs[1] else report_kwargs[0][1]
    assert "my_prompt" in payload["hashes"]
    assert payload["drifted"] == []


@pytest.mark.asyncio
async def test_run_detects_drift(tmp_path: Path) -> None:
    """run() posts a drift finding when current hash differs from baseline."""
    prompts_root = tmp_path / "prompts"
    _write_prompt(prompts_root, "my_prompt", "New content.")

    sensor, publisher, _ = _make_sensor(prompts_root)

    governed = [{"name": "my_prompt", "anchors": ["ADR-134"]}]
    prior_baseline = {"hashes": {"my_prompt": "aabbccdd" * 8}}  # stale hash

    with (
        patch.object(sensor, "_load_governed_prompts", return_value=governed),
        patch.object(sensor, "_fetch_baseline", new_callable=AsyncMock, return_value=prior_baseline),
        patch("shared.infrastructure.settings.settings") as mock_settings,
    ):
        mock_settings.paths.prompts_dir = prompts_root
        await sensor.run()

    publisher.post_finding.assert_called_once()
    call_kwargs = publisher.post_finding.call_args
    subject = call_kwargs[1].get("subject") or call_kwargs[0][0]
    assert "my_prompt" in subject
    payload = call_kwargs[1].get("payload") or call_kwargs[0][1]
    assert payload["rule"] == "ai.prompt.governed_change_requires_review"
