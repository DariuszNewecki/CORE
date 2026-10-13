# src/will/workers/thesis_sensor.py
"""
ThesisSensor — measures the thesis daily and keeps the weekly evidence.

The thesis and its rules: .specs/DECISIONS.md, "Thesis and baselines
(2026-10-13)"; the rules in code: shared.thesis_rules.

Once per day (the sensor wakes hourly; a day already recorded is skipped):
measure the four numbers, store them as the day's report
(``thesis.measures::<date>``, with the governor's line and every
unverified write ever found, so none is lost to a window), and raise one
blocking finding per broken measure (``thesis.broken::<measure>``), resolved
on the first day the measure holds again. On Mondays: append the week that
just ended to the GitHub branch ``evidence`` (append-only, never main).

Constitutional standing:
- Declaration: .intent/workers/thesis_sensor.yaml
- Phase: audit; no LLM; approval: false
- DB, GitHub and git through Body (body.services.thesis).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from shared.logger import getLogger
from shared.thesis_rules import (
    BROKEN_SUBJECT,
    EVIDENCE_SUBJECT,
    MEASURES,
    MEASURES_SUBJECT,
    UNVERIFIED_KEY,
    Breach,
    ThesisMeasures,
    breaches,
    report_line,
    stored_unverified,
    week_label,
)
from shared.workers.base import Worker


logger = getLogger(__name__)


# ID: 9fa64743-aa04-425a-82df-4a52b2e51153
async def guard_breaches(
    worker: Any, blackboard: Any, measures: ThesisMeasures, found: list[Breach]
) -> None:
    """One blocking finding per broken measure, raised once; a measure that
    holds again (and could be read) resolves its finding."""
    active = await blackboard.fetch_active_finding_subjects_by_prefix(
        f"{BROKEN_SUBJECT}%"
    )
    broken = {f"{BROKEN_SUBJECT}{b.measure}": b for b in found}
    for subject, breach in broken.items():
        if subject in active:
            continue
        await worker.post_observation(
            subject=subject,
            payload={
                "severity": "block",
                "measure": breach.measure,
                "value": getattr(measures, breach.measure),
                "day": measures.day.isoformat(),
                "message": breach.message,
                "rule": '.specs/DECISIONS.md, "Thesis and baselines (2026-10-13)"',
            },
            status="indeterminate",
        )
    for name in MEASURES:
        subject = f"{BROKEN_SUBJECT}{name}"
        if (
            subject in active
            and subject not in broken
            and getattr(measures, name) is not None
        ):
            await blackboard.adjudicate_indeterminate_findings(
                subject_prefix=subject,
                current_violation_subjects=set(),
                resolved_by="thesis_sensor",
            )


# ID: cfdc3f69-64f1-4bf1-9759-39b84ec78661
def week_records(records: list[dict[str, Any]], monday: date) -> tuple[str, list]:
    """The ISO week before *monday* and its stored daily records."""
    start = monday - timedelta(days=7)
    days = {(start + timedelta(days=i)).isoformat() for i in range(7)}
    return week_label(start), [r for r in records if r.get("day") in days]


# ID: a6b33a16-1d6b-4e4b-832e-0dfcc665d838
class ThesisSensor(Worker):
    """Daily thesis measures, breaches as blocking findings, weekly evidence."""

    declaration_name = "thesis_sensor"

    def __init__(self, core_context: Any) -> None:
        super().__init__()
        self._core_context = core_context

    # ID: d55530ed-1851-41c2-a703-e4307e14148b
    async def run(self) -> None:
        """Measure today once; on Mondays push last week's evidence once."""
        from body.services.thesis import runtime

        await self.post_heartbeat()
        today = datetime.now(UTC).date()
        records = await runtime.daily_records()
        if not any(r.get("day") == today.isoformat() for r in records):
            records.append(await self._measure(today, records))
        if today.weekday() == 0:
            await self._push_evidence(today, records)

    async def _measure(self, today: date, records: list[dict[str, Any]]) -> dict:
        from body.services.thesis import runtime

        taken = await runtime.measure_today(
            today, self._core_context.git_service, stored_unverified(records)
        )
        history = [ThesisMeasures.from_payload(r) for r in records]
        found = breaches(taken.measures, history)
        payload = {
            **taken.measures.as_payload(),
            "line": report_line(taken.measures),
            "breaches": [{"measure": b.measure, "message": b.message} for b in found],
            "unavailable": taken.unavailable,
            "detail": taken.detail,
            UNVERIFIED_KEY: taken.unverified_breaches,
        }
        await self.post_report(subject=f"{MEASURES_SUBJECT}{today}", payload=payload)
        blackboard = await self._core_context.registry.get_blackboard_service()
        await guard_breaches(self, blackboard, taken.measures, found)
        logger.info("%s; breaches: %d", payload["line"], len(found))
        return payload

    async def _push_evidence(self, today: date, records: list[dict[str, Any]]) -> None:
        from body.services.thesis import runtime

        week, days = week_records(records, today)
        if not days or week in await runtime.evidence_weeks():
            return
        try:
            sha = await runtime.push_week(week, days)
        except Exception as exc:  # retried on the next hourly run
            logger.warning("thesis: evidence push for %s failed: %s", week, exc)
            return
        await self.post_report(
            subject=f"{EVIDENCE_SUBJECT}{week}",
            payload={"week": week, "commit": sha, "days": len(days)},
        )
