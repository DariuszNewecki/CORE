# tests/body/services/test_health_log_service__convergence_artifact.py
"""Unit tests for HealthLogService._append_convergence_artifact (P1.5-#8).

Instruments the rolling JSONL convergence artifact shipped in f6f530a2.
Tests cover:

  - New-file path: no existing artifact → single-entry file written.
  - Existing-file path: entries read, rolling window applied, new entry appended.
  - Window trimming: >29 existing entries trimmed to last 29 + new entry = 30 lines.
  - Fail-soft: FileHandler error is swallowed; no exception propagates.
  - Key extraction: entry carries exactly the four expected keys.

No DB, no daemon. bootstrap_registry and FileHandler are patched so the test
runs without a real repo on disk.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from body.services.health_log_service import (
    _CONVERGENCE_ROLLING_WINDOW,
    HealthLogService,
)


_STATE = {
    "observed_at": "2026-07-02T10:00:00+00:00",
    "open_findings": 5,
    "governor_inbox": 3,
    "flow_24h": {"proposals_completed": 2},
}


def _make_service(tmp_path: Path) -> tuple[HealthLogService, MagicMock]:
    """Return (service, mock_file_handler) with bootstrap_registry patched to tmp_path."""
    svc = HealthLogService()
    mock_fh = MagicMock()
    return svc, mock_fh


def _run_append(
    svc: HealthLogService,
    tmp_path: Path,
    mock_fh: MagicMock,
    state: dict | None = None,
) -> str | None:
    """Invoke _append_convergence_artifact; return the content written to FileHandler."""
    written: dict[str, str] = {}

    def capture_write(rel_path: str, content: str) -> None:
        written["rel_path"] = rel_path
        written["content"] = content

    mock_fh.write_runtime_text.side_effect = capture_write

    with (
        patch(
            "body.services.health_log_service.bootstrap_registry.get_repo_path",
            return_value=tmp_path,
        ),
        patch(
            "body.infrastructure.storage.file_handler.FileHandler",
            return_value=mock_fh,
        ),
    ):
        svc._append_convergence_artifact(state or _STATE)

    return written.get("content")


def test_new_file_writes_single_entry(tmp_path: Path) -> None:
    svc, mock_fh = _make_service(tmp_path)
    content = _run_append(svc, tmp_path, mock_fh)
    assert content is not None
    lines = [ln for ln in content.splitlines() if ln.strip()]
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["open_findings"] == 5
    assert entry["governor_inbox"] == 3
    assert entry["observed_at"] == _STATE["observed_at"]
    assert "flow_24h" in entry


def test_entry_written_to_correct_path(tmp_path: Path) -> None:
    svc, mock_fh = _make_service(tmp_path)
    _run_append(svc, tmp_path, mock_fh)
    mock_fh.write_runtime_text.assert_called_once()
    rel_path = mock_fh.write_runtime_text.call_args[0][0]
    assert rel_path == "var/reports/convergence.jsonl"


def test_existing_entries_preserved_and_new_appended(tmp_path: Path) -> None:
    artifact_path = tmp_path / "var" / "reports" / "convergence.jsonl"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    existing_entries = [
        json.dumps(
            {
                "observed_at": f"t{i}",
                "open_findings": i,
                "governor_inbox": 0,
                "flow_24h": {},
            }
        )
        for i in range(5)
    ]
    artifact_path.write_text("\n".join(existing_entries), encoding="utf-8")

    svc, mock_fh = _make_service(tmp_path)
    content = _run_append(svc, tmp_path, mock_fh)
    assert content is not None
    lines = [ln for ln in content.splitlines() if ln.strip()]
    assert len(lines) == 6
    last = json.loads(lines[-1])
    assert last["open_findings"] == _STATE["open_findings"]


def test_rolling_window_trims_to_max(tmp_path: Path) -> None:
    artifact_path = tmp_path / "var" / "reports" / "convergence.jsonl"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    # Fill to exactly one more than the window so trimming fires
    overflow = _CONVERGENCE_ROLLING_WINDOW + 5
    existing_entries = [
        json.dumps(
            {
                "observed_at": f"t{i}",
                "open_findings": i,
                "governor_inbox": 0,
                "flow_24h": {},
            }
        )
        for i in range(overflow)
    ]
    artifact_path.write_text("\n".join(existing_entries), encoding="utf-8")

    svc, mock_fh = _make_service(tmp_path)
    content = _run_append(svc, tmp_path, mock_fh)
    assert content is not None
    lines = [ln for ln in content.splitlines() if ln.strip()]
    assert len(lines) == _CONVERGENCE_ROLLING_WINDOW


def test_fail_soft_on_file_handler_error(tmp_path: Path) -> None:
    svc = HealthLogService()
    mock_fh = MagicMock()
    mock_fh.write_runtime_text.side_effect = OSError("disk full")

    with (
        patch(
            "body.services.health_log_service.bootstrap_registry.get_repo_path",
            return_value=tmp_path,
        ),
        patch(
            "body.infrastructure.storage.file_handler.FileHandler",
            return_value=mock_fh,
        ),
    ):
        # Must not raise
        svc._append_convergence_artifact(_STATE)
