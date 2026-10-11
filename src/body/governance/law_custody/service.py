# src/body/governance/law_custody/service.py
"""
``law apply`` in two steps: prepare (read, check, warn) and apply (write).

The CLI shows what ``prepare`` returns, asks the governor to type the
proposal id, and only then calls ``apply_prepared`` with the same in-memory
snapshot (ADR-170 D3 step 3).

``apply_prepared`` signs the ledger line *before* writing anything, so a
signing failure writes nothing; it refuses when a destination's current
bytes changed after the report was shown; it writes every destination and
appends the ledger line only when every write succeeded.

CONSTITUTIONAL ALIGNMENT:
- Writes only through ``writer`` (the custodian's surface).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from body.governance.law_custody.checks import run_checks_in_child
from body.governance.law_custody.law_warnings import LawWarning, compute_warnings
from body.governance.law_custody.ledger import build_ledger_line, signed_line_bytes
from body.governance.law_custody.proposal import LawProposal, read_proposal
from body.governance.law_custody.writer import (
    CUSTODIAN_ACCOUNT,
    CustodyError,
    DestinationOutcome,
    append_ledger,
    build_scratch_tree,
    remove_scratch_tree,
    write_destinations,
)
from shared.infrastructure.intent.governed_text import load_governed_text_paths


@dataclass
# ID: 8c4b4d26-7be2-4149-ba5f-8e422d792b55
class PreparedApply:
    """Everything the governor is shown, held in memory until the typed id."""

    proposal: LawProposal
    repo_root: Path
    destinations: list[Path]
    old: dict[str, bytes | None]
    checks: dict[str, Any]
    refusals: list[dict[str, str]]
    computed_warnings: list[LawWarning]
    shown_utc: str


@dataclass
# ID: 2e827c5f-4204-4cdb-9347-c7db0e421085
class ApplyOutcome:
    """What was written where, and the ledger line if one was appended."""

    outcomes: list[DestinationOutcome] = field(default_factory=list)
    ledger_line: bytes | None = None

    # ID: 8b70e822-e638-40d2-8969-c2e4b6bda410
    def ok(self) -> bool:
        """Every destination written and the ledger line appended."""
        return self.ledger_line is not None and all(
            o.failed is None for o in self.outcomes
        )


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# ID: 044e99e0-0a4b-42d3-a1db-9e3199479761
def read_current(root: Path, paths: Sequence[str]) -> dict[str, bytes | None]:
    """Current bytes of each path under *root* (``None`` when absent)."""
    current: dict[str, bytes | None] = {}
    for rel in paths:
        target = root / rel
        current[rel] = target.read_bytes() if target.is_file() else None
    return current


# ID: ec9b4d06-c1f5-4088-b602-e5b825ad4ba8
def prepare(
    *,
    repo_root: Path,
    proposals_dir: Path,
    proposal_id: str,
    destinations: Sequence[Path],
    scratch_parent: Path,
    custodian: str = CUSTODIAN_ACCOUNT,
    run_checks: Callable[[Path], dict[str, Any]] = run_checks_in_child,
) -> PreparedApply:
    """Read the proposal once, check it on a scratch tree, compute warnings."""
    proposal = read_proposal(proposals_dir, proposal_id, load_governed_text_paths())
    old = read_current(repo_root, proposal.paths())
    tree = build_scratch_tree(repo_root, scratch_parent, proposal, custodian=custodian)
    try:
        report = run_checks(tree)
    finally:
        remove_scratch_tree(tree)
    new: dict[str, bytes | None] = {f.path: f.content for f in proposal.files}
    new.update({path: None for path in proposal.removals})
    return PreparedApply(
        proposal=proposal,
        repo_root=repo_root,
        destinations=list(destinations),
        old=old,
        checks=dict(report.get("checks") or {}),
        refusals=list(report.get("refusals") or []),
        computed_warnings=compute_warnings(old, new),
        shown_utc=_utc_now(),
    )


# ID: abfd270e-e1e0-4027-bf61-54add9cade5e
def apply_prepared(
    prepared: PreparedApply,
    *,
    approver: str,
    key_path: Path,
    custodian: str = CUSTODIAN_ACCOUNT,
) -> ApplyOutcome:
    """Write the prepared proposal to every destination and append the ledger."""
    if prepared.refusals:
        raise CustodyError("the checks refused this proposal; nothing is written")
    if read_current(prepared.repo_root, prepared.proposal.paths()) != prepared.old:
        raise CustodyError(
            "governed text changed after the report was shown; run law apply again"
        )
    line = build_ledger_line(
        proposal=prepared.proposal,
        approver=approver,
        shown_utc=prepared.shown_utc,
        approved_utc=_utc_now(),
        destinations=prepared.destinations,
        checks=prepared.checks,
        computed_warnings=prepared.computed_warnings,
        old=prepared.old,
    )
    signed = signed_line_bytes(line, key_path)
    outcomes = write_destinations(
        prepared.destinations, prepared.proposal, custodian=custodian
    )
    result = ApplyOutcome(outcomes=outcomes)
    if len(outcomes) == len(prepared.destinations) and all(
        o.failed is None for o in outcomes
    ):
        append_ledger(prepared.destinations, signed, custodian=custodian)
        result.ledger_line = signed
    return result
