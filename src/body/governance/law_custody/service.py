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

import hashlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from body.governance.law_custody.checks import run_checks_in_child
from body.governance.law_custody.law_warnings import LawWarning, compute_warnings
from body.governance.law_custody.ledger import (
    REMOVED,
    build_ledger_line,
    recorded_hashes,
    signed_line_bytes,
)
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
from shared.infrastructure.git_service import GitService
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
    #: What the ledger counts changes against: ``old``, except for a path an
    #: earlier failed attempt already wrote, which is compared with its last
    #: committed version (#966).
    baseline: dict[str, bytes | None] = field(default_factory=dict)


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
    code_tree: Path | None = None,
) -> PreparedApply:
    """Read the proposal once, check it on a scratch tree, compute warnings.

    *code_tree*, when given, is the code the proposal is checked against
    (the commit it comes from); otherwise the code in *repo_root*.
    """
    proposal = read_proposal(proposals_dir, proposal_id, load_governed_text_paths())
    old = read_current(repo_root, proposal.paths())
    tree = build_scratch_tree(
        repo_root, scratch_parent, proposal, custodian=custodian, code_tree=code_tree
    )
    try:
        report = run_checks(tree)
    finally:
        remove_scratch_tree(tree)
    new: dict[str, bytes | None] = {f.path: f.content for f in proposal.files}
    new.update({path: None for path in proposal.removals})
    baseline, unrecorded = rerun_baseline(repo_root, old, new)
    return PreparedApply(
        proposal=proposal,
        repo_root=repo_root,
        destinations=list(destinations),
        old=old,
        checks=dict(report.get("checks") or {}),
        refusals=list(report.get("refusals") or []),
        computed_warnings=compute_warnings(baseline, new) + unrecorded,
        shown_utc=_utc_now(),
        baseline=baseline,
    )


# ID: ba8f8bce-64bd-4488-8b7a-1e03e4817400
def rerun_baseline(
    repo_root: Path,
    old: dict[str, bytes | None],
    new: dict[str, bytes | None],
) -> tuple[dict[str, bytes | None], list[LawWarning]]:
    """What a proposal is compared against, and the paths a failed attempt wrote.

    #966: a failed ``--write`` leaves the new bytes in the destinations it
    reached and records no ledger line. A rerun then read those bytes as
    the current law: its report and ledger line compared new with new
    (lines_changed 0, the assistant_contract warning of 0025 lost). A path
    whose current bytes already equal the proposal's, with that hash in no
    ledger line, is such a leftover: it is compared with its last committed
    version (git HEAD) and named in a warning, so the governor sees it.
    """
    baseline = dict(old)
    warnings: list[LawWarning] = []
    recorded = recorded_hashes(repo_root)
    for path, content in sorted(new.items()):
        if old.get(path) != content:
            continue
        mark = REMOVED if content is None else hashlib.sha256(content).hexdigest()
        if mark in recorded.get(path, set()):
            continue
        committed = _committed_bytes(repo_root, path)
        note = "compared with its last committed version"
        if committed is _UNKNOWN:
            note = "its earlier version is unknown (no git); compared with itself"
        else:
            baseline[path] = committed  # type: ignore[assignment]
        warnings.append(
            LawWarning(
                "unrecorded_prior_write",
                path,
                (
                    "is already removed"
                    if content is None
                    else "already holds these bytes"
                )
                + " from an earlier attempt that wrote no ledger line; "
                + note,
            )
        )
    return baseline, warnings


_UNKNOWN = object()


def _committed_bytes(repo_root: Path, rel: str) -> object:
    """``rel`` at git HEAD in ``repo_root``; None when HEAD has no such file;
    ``_UNKNOWN`` when git cannot answer."""
    try:
        return GitService(repo_root).committed_bytes(rel)
    except RuntimeError:
        return _UNKNOWN


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
        old=prepared.baseline or prepared.old,
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


# The ledger approver for a proposal applied without typed approval.
AUTO_APPROVER = "auto:record-only"
_RECORD_ROOT = ".specs/"


# ID: e53576aa-692b-49e2-bd72-a267f6a301f6
def record_only_refusal(prepared: PreparedApply) -> str | None:
    """Why *prepared* needs the governor's typed approval, or None.

    A record-only proposal (governor redesign 2026-10-12) changes no rule: it
    only adds or edits text under ``.specs/`` (decisions, papers, records of
    built code), removes nothing, and CORE computes no warning for it. Any
    rule, the assistant's own contract, a removal or a weakening needs the
    typed id.
    """
    if prepared.refusals:
        return "the checks refused it"
    proposal = prepared.proposal
    if proposal.removals:
        return "it removes files"
    outside = [p for p in proposal.paths() if not p.startswith(_RECORD_ROOT)]
    if outside:
        return "it changes more than .specs/: " + ", ".join(outside)
    if prepared.computed_warnings:
        return "CORE computed warnings: " + "; ".join(
            f"{w.category} ({w.path})" for w in prepared.computed_warnings
        )
    return None
