# src/body/services/thesis/runtime.py
"""The thesis sensor's entry points into Body: GitHub, measuring
and the weekly evidence push."""

from __future__ import annotations

from datetime import date
from typing import Any

import httpx

from body.infrastructure.thesis_config import thesis_config
from body.services.thesis import measure as measure_module
from body.services.thesis import record
from body.services.thesis.github import GitHub


# ID: 04fd8c20-a858-4112-a892-5af948401efd
async def measure_today(day: date, git_service: Any) -> measure_module.Measurement:
    """Measure *day* against CORE's clone of the merge branch."""
    from body.infrastructure.repo_sync import upstream_branch

    config = thesis_config()
    async with httpx.AsyncClient() as client:
        gh = GitHub(config.repo, config.token, client)
        return await measure_module.measure(
            day,
            gh,
            git_service,
            f"refs/remotes/upstream/{upstream_branch()}",
            config.transcripts,
        )


# ID: 52fffdc9-3871-4f27-924f-04174f5f3905
async def push_week(week: str, records: list[dict[str, Any]]) -> str | None:
    """Append one week's daily records to the evidence branch."""
    config = thesis_config()
    async with httpx.AsyncClient() as client:
        gh = GitHub(config.repo, config.token, client)
        return await record.push_evidence_week(gh, week, records)


daily_records = record.daily_records
evidence_weeks = record.evidence_weeks
