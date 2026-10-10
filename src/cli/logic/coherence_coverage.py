# src/cli/logic/coherence_coverage.py

"""
Which CCC check classes actually ran in a coherence run.

The run manifest has recorded each check class's outcome since #624 (a
``_meta`` entry, ``type: check_classes_run``), but `coherence check` and
`coherence report` only counted *input items*. A run whose contradiction
checks (SAMECONCERN, R1_SCOPED) were skipped printed "0 skipped" — a
partial check presenting as whole (same class as #952/#956). Both commands
read the check-class outcome through this helper and say so plainly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


__all__ = ["CheckClassCoverage", "check_class_coverage", "coverage_lines"]


@dataclass(frozen=True)
# ID: 64ed54d1-eca5-44b9-a295-d5f018527000
class CheckClassCoverage:
    """Outcome of every check class in one run."""

    ran: list[str] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)
    recorded: bool = True
    """False when the manifest carries no check-class record (pre-#624 runs)."""
    carried_forward: int = 0
    """Candidates not raised again: identical to a dismissed one, documents
    unchanged since triage (ADR-067 note 2026-10-10)."""

    @property
    # ID: 985fbfec-303e-4fb4-9a08-a078b0b8f663
    def partial(self) -> bool:
        """True when any check class did not run, or nothing says which ran."""
        return bool(self.skipped or self.failed) or not self.recorded


# ID: 0d80eb52-224e-4185-beb5-253c3c9e40a4
def check_class_coverage(manifest: list[dict[str, Any]]) -> CheckClassCoverage:
    """Read the check-class outcome recorded in a run's input manifest."""
    record = next(
        (
            e
            for e in manifest
            if e.get("domain") == "_meta" and e.get("type") == "check_classes_run"
        ),
        None,
    )
    if record is None:
        return CheckClassCoverage(recorded=False)

    ran: list[str] = []
    skipped: list[tuple[str, str]] = []
    failed: list[tuple[str, str]] = []
    carried = 0
    for name, outcome in sorted((record.get("check_status") or {}).items()):
        status = (outcome or {}).get("status")
        carried += int((outcome or {}).get("carried_forward") or 0)
        if status == "ok":
            ran.append(name)
        elif status == "skipped":
            skipped.append((name, str(outcome.get("reason") or "")))
        elif status == "partial":
            failed.append((name, f"incomplete — {outcome.get('error') or ''}"))
        else:
            failed.append((name, str(outcome.get("error") or status or "unknown")))
    return CheckClassCoverage(
        ran=ran, skipped=skipped, failed=failed, carried_forward=carried
    )


# ID: f96202f7-d009-4c3a-9e9a-c97b4dc264ec
def coverage_lines(coverage: CheckClassCoverage) -> list[str]:
    """Plain-text lines naming what ran and, loudly, what did not."""
    if not coverage.recorded:
        return [
            "Check classes: not recorded for this run — which checks ran is "
            "unknown; treat it as partial."
        ]
    lines = [
        f"Check classes: {len(coverage.ran)} ran, {len(coverage.skipped)} "
        f"skipped, {len(coverage.failed)} failed"
    ]
    if coverage.carried_forward:
        lines.append(
            f"  {coverage.carried_forward} candidate(s) carried forward as dismissed "
            "(identical, documents unchanged since triage)"
        )
    for name, reason in coverage.skipped:
        lines.append(f"  SKIPPED {name}: {reason}")
    for name, error in coverage.failed:
        lines.append(f"  FAILED  {name}: {error}")
    if coverage.partial:
        lines.append(
            "PARTIAL RUN: the checks above did not run. Their concerns are "
            "unchecked, not clear."
        )
    return lines
