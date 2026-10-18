# src/shared/thesis_rules.py
"""The thesis measures and the rules that would refute the thesis.

Source: .specs/DECISIONS.md, "Thesis and baselines (2026-10-13)". A
non-programmer governs untrusted AI through deterministic checks and ships
working software, at a governance cost that falls over time. Four measures,
taken daily by the thesis sensor:

- unverified_writes: writes to main since the one-path cutover (2026-10-12)
  that the runner (infra/core-pipeline) would not deploy: not a pull request
  the governor merged or whose exact last commit the governor approved, or
  CI not green. From the promotion cutover (ADR-171: the moment of the
  first deploy recorded with its promotion) main is integration and its writes no
  longer count; the writes that count are the deploys, each verified only
  when it ran a promotion into live whose exact head the governor approved.
  Any is a breach. Each breach is kept for good in the daily reports
  (``unverified_breaches``) and counted every day after, never dropped by a
  window.
- ai_share: AI-authored share of commits merged into main (30 days); below
  the 63% baseline is a breach.
- waste_per_change: round trips that reached the governor or Claude Code
  without moving main, per write to main (14 days); higher than a month
  earlier (or than the 2.0 baseline before a month of history) is a breach.
- convergence: findings resolved (not abandoned) / findings created (30
  days). Below 100% is a breach only once it has reached 100%, and only when
  it was also below 100% a month earlier (two consecutive months).

A measure whose source could not be read is None: never a breach, never a
pass. Pure: no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any


CUTOVER = date(2026, 10, 12)
AI_SHARE_FLOOR = 0.63
WASTE_BASELINE = 2.0
CONVERGENCE_TARGET = 1.0
MONTH = timedelta(days=30)
MEASURES = ("unverified_writes", "ai_share", "waste_per_change", "convergence")
MEASURES_SUBJECT = "thesis.measures::"
EVIDENCE_SUBJECT = "thesis.evidence::"
BROKEN_SUBJECT = "thesis.broken::"
UNVERIFIED_KEY = "unverified_breaches"
CORRECTIONS_KEY = "unverified_corrections"


@dataclass(frozen=True)
# ID: 87dace8f-dc78-481a-ab53-306268eb0ec5
class ThesisMeasures:
    """One day's four numbers; None where the source could not be read."""

    day: date
    unverified_writes: int | None
    ai_share: float | None
    waste_per_change: float | None
    convergence: float | None

    # ID: db1543d6-3b63-4755-b6b0-3bc587ea716a
    def as_payload(self) -> dict[str, Any]:
        """The fields stored with the daily report."""
        return {
            "day": self.day.isoformat(),
            **{name: getattr(self, name) for name in MEASURES},
        }

    @classmethod
    # ID: 343eb1c7-1cd1-49b7-bdd1-3949b19f49e0
    def from_payload(cls, payload: dict[str, Any]) -> ThesisMeasures:
        """Read back a stored daily report."""
        return cls(
            day=date.fromisoformat(str(payload["day"])),
            **{name: payload.get(name) for name in MEASURES},
        )


@dataclass(frozen=True)
# ID: 1242aebf-4cc3-4289-a3af-dc215740133d
class Breach:
    """A measure that broke its rule today."""

    measure: str
    message: str


# ID: 24af845e-793b-46c6-a171-341e281820ea
def stored_unverified(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every unverified write ever stored in the daily reports, once per sha,
    with the day it was first seen, oldest first; only those since CUTOVER.
    A breach named false by a correction row (CORRECTIONS_KEY, in any later
    report) is left out; the row that stored it stays as it was."""
    corrected = {
        str(c.get("sha", ""))
        for record in records
        for c in record.get(CORRECTIONS_KEY) or []
    }
    found: dict[str, dict[str, Any]] = {}
    for record in records:
        for breach in record.get(UNVERIFIED_KEY) or []:
            sha = str(breach.get("sha", ""))
            seen = str(breach.get("first_seen", ""))
            if not sha or sha in corrected or seen < CUTOVER.isoformat():
                continue
            if sha not in found or seen < str(found[sha]["first_seen"]):
                found[sha] = dict(breach)
    return sorted(found.values(), key=lambda b: (str(b["first_seen"]), b["sha"]))


def _month_before(history: list[ThesisMeasures], day: date) -> ThesisMeasures | None:
    earlier = [r for r in history if r.day <= day - MONTH]
    return max(earlier, key=lambda r: r.day) if earlier else None


# ID: 2f26d110-dc45-47c0-95d4-de0b56c450fe
def breaches(today: ThesisMeasures, history: list[ThesisMeasures]) -> list[Breach]:
    """The rules of the thesis entry applied to today's numbers.

    *history* holds earlier days (today's own record, if present, is ignored).
    """
    past = [r for r in history if r.day < today.day]
    found: list[Breach] = []
    if today.unverified_writes:
        found.append(
            Breach(
                "unverified_writes",
                f"{today.unverified_writes} write(s) reached main since "
                f"{CUTOVER.isoformat()} without green CI and the governor's "
                "approval of the pull request's last commit (or merge).",
            )
        )
    if today.ai_share is not None and today.ai_share < AI_SHARE_FLOOR:
        found.append(
            Breach(
                "ai_share",
                f"AI authorship fell to {today.ai_share:.0%}, below the "
                f"{AI_SHARE_FLOOR:.0%} floor.",
            )
        )
    prior = _month_before(past, today.day)
    if today.waste_per_change is not None:
        reference = (
            prior.waste_per_change
            if prior is not None and prior.waste_per_change is not None
            else WASTE_BASELINE
        )
        if today.waste_per_change > reference:
            found.append(
                Breach(
                    "waste_per_change",
                    f"Waste rose to {today.waste_per_change} trips per merged "
                    f"change, from {reference} a month earlier.",
                )
            )
    if today.convergence is not None and today.convergence < CONVERGENCE_TARGET:
        reached = any(
            r.convergence is not None and r.convergence >= CONVERGENCE_TARGET
            for r in past
        )
        if (
            reached
            and prior is not None
            and prior.convergence is not None
            and prior.convergence < CONVERGENCE_TARGET
        ):
            found.append(
                Breach(
                    "convergence",
                    f"Convergence is {today.convergence:.0%}, below 100% for a "
                    "second consecutive month after having reached it.",
                )
            )
    return found


def _show(value: float | int | None, percent: bool = False) -> str:
    if value is None:
        return "unavailable"
    return f"{value:.0%}" if percent else str(value)


# ID: c0cae882-029d-4a19-a56f-2ca8719dcce6
def report_line(measures: ThesisMeasures) -> str:
    """The governor's daily line: the four numbers, plainly."""
    return (
        f"thesis {measures.day.isoformat()}: "
        f"unverified writes {_show(measures.unverified_writes)} · "
        f"AI authorship {_show(measures.ai_share, percent=True)} · "
        f"waste {_show(measures.waste_per_change)} per change · "
        f"convergence {_show(measures.convergence, percent=True)}"
    )


# ID: 92652139-2b1f-4045-8306-db6848e7d5f1
def week_label(day: date) -> str:
    """ISO week of *day*, e.g. ``2026-W42``."""
    year, week, _ = day.isocalendar()
    return f"{year}-W{week:02d}"
