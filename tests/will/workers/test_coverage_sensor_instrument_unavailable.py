"""TestCoverageSensor must post an instrument-unavailable observation — not a
false all-clear — when the coverage scan can't run (#765/T1.3).

Worker.__init__ reads .intent/, so instances are built via object.__new__ and
the minimal attributes set by hand (same pattern as the other worker unit
tests in this session).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

from shared.infrastructure.intent.test_coverage_paths import InstrumentUnavailable
from will.workers.test_coverage_sensor import TestCoverageSensor


def _make_sensor() -> TestCoverageSensor:
    w = object.__new__(TestCoverageSensor)
    w._declaration = {}
    w._max_interval = 300
    w._artifact_type = "python"
    w._rule_namespace = "test.coverage"
    w._repo_root = Path("/repo")
    w._core_context = None
    w.post_heartbeat = AsyncMock()
    w.post_report = AsyncMock()
    w.post_unavailable = AsyncMock()
    w.post_artifact_finding = AsyncMock()
    return w


async def test_scan_unavailable_posts_unavailable_not_allclear() -> None:
    sensor = _make_sensor()

    with (
        patch.object(sensor, "_load_coverage_config", return_value={}),
        patch.object(
            sensor,
            "_scan_uncovered_files",
            side_effect=InstrumentUnavailable("source root not found"),
        ),
    ):
        await sensor.run()

    # The false all-clear report must NOT be posted.
    sensor.post_report.assert_not_awaited()
    # The instrument-unavailable observation MUST be posted.
    sensor.post_unavailable.assert_awaited_once()
    call = sensor.post_unavailable.await_args
    assert "source root not found" in call.kwargs["reason"]


async def test_genuinely_clean_still_posts_allclear() -> None:
    """A successful scan returning nothing uncovered still posts the
    all-clear report — the honest-clean path is unchanged."""
    sensor = _make_sensor()

    with (
        patch.object(sensor, "_load_coverage_config", return_value={}),
        patch.object(sensor, "_scan_uncovered_files", return_value=[]),
    ):
        await sensor.run()

    sensor.post_unavailable.assert_not_awaited()
    sensor.post_report.assert_awaited_once()
    payload = sensor.post_report.await_args.kwargs["payload"]
    assert payload["uncovered"] == 0
