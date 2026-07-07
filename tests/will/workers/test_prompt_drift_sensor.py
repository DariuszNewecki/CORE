"""Tests for PromptDriftSensor (ADR-134 D6).

Verifies:
- _compute_hashes returns a stable combined SHA-256 and per-file hashes
- _compute_hashes returns (None, {}) for a missing prompt directory
- _compute_hashes covers system.txt, user.txt, AND model.yaml (ADR-134)
- run() posts a baseline report and no findings on the first cycle (no prior baseline)
- run() posts a drift finding when system.txt changes between cycles
- drift finding payload includes adr_anchor, changed_files, and git_commit (ADR-134 D6)
- _diff_file_hashes correctly identifies added, removed, and changed files
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_sensor(repo_root: Path, git_commit: str = "abc123") -> Any:
    """Instantiate PromptDriftSensor with Worker infrastructure mocked out."""
    from will.workers.prompt_drift_sensor import PromptDriftSensor

    decl: dict[str, Any] = {
        "kind": "worker",
        "metadata": {
            "id": "workers.prompt_drift_sensor",
            "title": "Prompt Drift Sensor",
        },
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
        patch(
            "shared.workers.blackboard_publisher.BlackboardPublisher.__init__",
            return_value=None,
        ),
    ):
        sensor = PromptDriftSensor.__new__(PromptDriftSensor)
        sensor._declaration = decl
        sensor._worker_uuid = uuid.uuid4()
        sensor._worker_name = "Prompt Drift Sensor"
        sensor._worker_class = "sensing"
        sensor._phase = "audit"
        sensor._approval_required = False
        sensor._max_interval = 900
        sensor._core_context = MagicMock()
        sensor._core_context.git_service.repo_path = repo_root
        sensor._core_context.git_service.get_current_commit.return_value = git_commit
        sensor._cycle_post_count = 0

    publisher = MagicMock()
    publisher.post_heartbeat = AsyncMock(return_value=uuid.uuid4())
    publisher.post_report = AsyncMock(return_value=uuid.uuid4())
    publisher.post_finding = AsyncMock(return_value=uuid.uuid4())
    sensor._blackboard = publisher

    prompts_root = repo_root / "var" / "prompts"
    return sensor, publisher, prompts_root


def _write_prompt(
    prompts_root: Path,
    name: str,
    system_txt: str,
    user_txt: str | None = None,
    model_yaml: str | None = None,
) -> None:
    d = prompts_root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "system.txt").write_text(system_txt)
    if user_txt is not None:
        (d / "user.txt").write_text(user_txt)
    if model_yaml is not None:
        (d / "model.yaml").write_text(model_yaml)


# ---------------------------------------------------------------------------
# _compute_hashes
# ---------------------------------------------------------------------------


def test_compute_hashes_stable(tmp_path: Path) -> None:
    """_compute_hashes returns the same combined digest on repeated calls."""
    sensor, _, prompts_root = _make_sensor(tmp_path)
    _write_prompt(prompts_root, "test_prompt", "You are a coder.")

    combined1, per_file1 = sensor._compute_hashes("test_prompt")
    combined2, per_file2 = sensor._compute_hashes("test_prompt")

    assert combined1 is not None
    assert combined1 == combined2
    assert len(combined1) == 64
    assert per_file1 == per_file2
    assert "system.txt" in per_file1


def test_compute_hashes_changes_on_content_change(tmp_path: Path) -> None:
    """_compute_hashes produces a different combined digest after system.txt changes."""
    sensor, _, prompts_root = _make_sensor(tmp_path)
    _write_prompt(prompts_root, "test_prompt", "Version 1.")

    combined1, _ = sensor._compute_hashes("test_prompt")
    (prompts_root / "test_prompt" / "system.txt").write_text("Version 2.")
    combined2, _ = sensor._compute_hashes("test_prompt")

    assert combined1 != combined2


def test_compute_hashes_returns_none_for_missing_dir(tmp_path: Path) -> None:
    """_compute_hashes returns (None, {}) when the prompt directory does not exist."""
    sensor, _, prompts_root = _make_sensor(tmp_path)
    prompts_root.mkdir(parents=True, exist_ok=True)

    combined, per_file = sensor._compute_hashes("nonexistent_prompt")

    assert combined is None
    assert per_file == {}


def test_compute_hashes_tracks_per_file(tmp_path: Path) -> None:
    """_compute_hashes records individual file hashes for system.txt and user.txt."""
    sensor, _, prompts_root = _make_sensor(tmp_path)
    _write_prompt(
        prompts_root, "test_prompt", "system content", user_txt="user content"
    )

    _, per_file = sensor._compute_hashes("test_prompt")

    assert "system.txt" in per_file
    assert "user.txt" in per_file
    assert per_file["system.txt"] != per_file["user.txt"]


def test_compute_hashes_tracks_model_yaml(tmp_path: Path) -> None:
    """_compute_hashes includes model.yaml in the per-file map when present (ADR-134)."""
    sensor, _, prompts_root = _make_sensor(tmp_path)
    _write_prompt(
        prompts_root,
        "test_prompt",
        "system content",
        model_yaml="model: gpt-4\nmax_tokens: 2048\n",
    )

    _, per_file = sensor._compute_hashes("test_prompt")

    assert "system.txt" in per_file
    assert "model.yaml" in per_file


def test_compute_hashes_changes_on_model_yaml_change(tmp_path: Path) -> None:
    """_compute_hashes combined digest changes when model.yaml changes (ADR-134)."""
    sensor, _, prompts_root = _make_sensor(tmp_path)
    _write_prompt(
        prompts_root,
        "test_prompt",
        "system content",
        model_yaml="model: gpt-4\nmax_tokens: 2048\n",
    )

    combined1, _ = sensor._compute_hashes("test_prompt")
    (prompts_root / "test_prompt" / "model.yaml").write_text(
        "model: gpt-4\nmax_tokens: 4096\n"
    )
    combined2, _ = sensor._compute_hashes("test_prompt")

    assert combined1 != combined2


# ---------------------------------------------------------------------------
# _diff_file_hashes
# ---------------------------------------------------------------------------


def test_diff_file_hashes_detects_changed_file() -> None:
    from will.workers.prompt_drift_sensor import _diff_file_hashes

    prior = {"system.txt": "aaa", "user.txt": "bbb"}
    current = {"system.txt": "aaa", "user.txt": "ccc"}
    assert _diff_file_hashes(prior, current) == ["user.txt"]


def test_diff_file_hashes_detects_added_file() -> None:
    from will.workers.prompt_drift_sensor import _diff_file_hashes

    prior = {"system.txt": "aaa"}
    current = {"system.txt": "aaa", "user.txt": "bbb"}
    assert _diff_file_hashes(prior, current) == ["user.txt"]


def test_diff_file_hashes_detects_removed_file() -> None:
    from will.workers.prompt_drift_sensor import _diff_file_hashes

    prior = {"system.txt": "aaa", "user.txt": "bbb"}
    current = {"system.txt": "aaa"}
    assert _diff_file_hashes(prior, current) == ["user.txt"]


def test_diff_file_hashes_empty_on_no_change() -> None:
    from will.workers.prompt_drift_sensor import _diff_file_hashes

    hashes = {"system.txt": "aaa", "user.txt": "bbb"}
    assert _diff_file_hashes(hashes, hashes) == []


# ---------------------------------------------------------------------------
# run() — first cycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_first_cycle_no_findings(tmp_path: Path) -> None:
    """On the first cycle (no baseline), run() posts a report and no findings."""
    sensor, publisher, prompts_root = _make_sensor(tmp_path)
    _write_prompt(prompts_root, "my_prompt", "System content.")

    governed = [{"name": "my_prompt", "anchors": ["ADR-134"]}]

    with (
        patch.object(sensor, "_load_governed_prompts", return_value=governed),
        patch.object(
            sensor, "_fetch_baseline", new_callable=AsyncMock, return_value=None
        ),
    ):
        await sensor.run()

    publisher.post_heartbeat.assert_called_once()
    publisher.post_report.assert_called_once()
    publisher.post_finding.assert_not_called()

    report_kwargs = publisher.post_report.call_args
    payload = report_kwargs[1]["payload"] if report_kwargs[1] else report_kwargs[0][1]
    assert "my_prompt" in payload["hashes"]
    assert "my_prompt" in payload["file_hashes"]
    assert payload["drifted"] == []


# ---------------------------------------------------------------------------
# run() — drift detected, payload fields
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_detects_drift(tmp_path: Path) -> None:
    """run() posts a drift finding when current hash differs from baseline."""
    sensor, publisher, prompts_root = _make_sensor(tmp_path)
    _write_prompt(prompts_root, "my_prompt", "New content.")

    governed = [{"name": "my_prompt", "anchors": ["ADR-134"]}]
    prior_baseline = {"hashes": {"my_prompt": "aabbccdd" * 8}, "file_hashes": {}}

    with (
        patch.object(sensor, "_load_governed_prompts", return_value=governed),
        patch.object(
            sensor,
            "_fetch_baseline",
            new_callable=AsyncMock,
            return_value=prior_baseline,
        ),
    ):
        await sensor.run()

    publisher.post_finding.assert_called_once()
    call_kwargs = publisher.post_finding.call_args
    subject = call_kwargs[1].get("subject") or call_kwargs[0][0]
    assert "my_prompt" in subject
    payload = call_kwargs[1].get("payload") or call_kwargs[0][1]
    assert payload["rule"] == "ai.prompt.governed_change_requires_review"


@pytest.mark.asyncio
async def test_run_drift_payload_includes_adr_anchor(tmp_path: Path) -> None:
    """Drift finding payload must include adr_anchor from governed_prompts.yaml."""
    sensor, publisher, prompts_root = _make_sensor(tmp_path)
    _write_prompt(prompts_root, "my_prompt", "New content.")

    governed = [{"name": "my_prompt", "anchors": ["ADR-134:D6", "ADR-003"]}]
    prior_baseline = {"hashes": {"my_prompt": "aabbccdd" * 8}, "file_hashes": {}}

    with (
        patch.object(sensor, "_load_governed_prompts", return_value=governed),
        patch.object(
            sensor,
            "_fetch_baseline",
            new_callable=AsyncMock,
            return_value=prior_baseline,
        ),
    ):
        await sensor.run()

    payload = publisher.post_finding.call_args[0][1]
    assert payload["adr_anchor"] == ["ADR-134:D6", "ADR-003"]


@pytest.mark.asyncio
async def test_run_drift_payload_includes_git_commit(tmp_path: Path) -> None:
    """Drift finding payload must include the current HEAD commit hash."""
    sensor, publisher, prompts_root = _make_sensor(tmp_path, git_commit="deadbeef")
    _write_prompt(prompts_root, "my_prompt", "New content.")

    governed = [{"name": "my_prompt", "anchors": ["ADR-134"]}]
    prior_baseline = {"hashes": {"my_prompt": "aabbccdd" * 8}, "file_hashes": {}}

    with (
        patch.object(sensor, "_load_governed_prompts", return_value=governed),
        patch.object(
            sensor,
            "_fetch_baseline",
            new_callable=AsyncMock,
            return_value=prior_baseline,
        ),
    ):
        await sensor.run()

    payload = publisher.post_finding.call_args[0][1]
    assert payload["git_commit"] == "deadbeef"


@pytest.mark.asyncio
async def test_run_drift_payload_includes_changed_files(tmp_path: Path) -> None:
    """Drift finding payload must list which prompt files changed."""
    sensor, publisher, prompts_root = _make_sensor(tmp_path)
    _write_prompt(prompts_root, "my_prompt", "New system content.")

    governed = [{"name": "my_prompt", "anchors": ["ADR-134"]}]
    # Prior baseline has a different system.txt hash, same structure
    prior_baseline = {
        "hashes": {"my_prompt": "aabbccdd" * 8},
        "file_hashes": {"my_prompt": {"system.txt": "oldoldhash" * 4}},
    }

    with (
        patch.object(sensor, "_load_governed_prompts", return_value=governed),
        patch.object(
            sensor,
            "_fetch_baseline",
            new_callable=AsyncMock,
            return_value=prior_baseline,
        ),
    ):
        await sensor.run()

    payload = publisher.post_finding.call_args[0][1]
    assert "system.txt" in payload["changed_files"]
