"""Tests for ``shared.protocols.blackboard_poster`` — the posting surface declared once."""

from __future__ import annotations

from typing import Any

from shared.protocols.blackboard_poster import ObservationPoster, ReportPoster


class _FullPoster:
    async def post_report(self, subject: str, payload: dict[str, Any]) -> Any:
        return ("report", subject)

    async def post_observation(
        self, subject: str, payload: dict[str, Any], *, status: str
    ) -> Any:
        return ("observation", subject, status)


def test_observation_poster_extends_report_poster() -> None:
    assert ReportPoster in ObservationPoster.__mro__
    assert hasattr(ObservationPoster, "post_report")
    assert hasattr(ObservationPoster, "post_observation")


def test_remediation_and_run_record_protocols_extend_it() -> None:
    from will.orchestration.goal_run_records import RunRecordPoster
    from will.remediation.blackboard import RemediationBlackboard

    assert ObservationPoster in RemediationBlackboard.__mro__
    assert ReportPoster in RunRecordPoster.__mro__


async def test_structural_poster_is_usable() -> None:
    poster: ObservationPoster = _FullPoster()
    assert await poster.post_report("s", {}) == ("report", "s")
    assert await poster.post_observation("s", {}, status="open") == (
        "observation",
        "s",
        "open",
    )
