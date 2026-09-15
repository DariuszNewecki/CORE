# src/body/services/blackboard_service/blackboard_run_export.py
"""
Deterministic export of one goal-driven run's Blackboard record (#893).

Responsibility: turn the rows ``BlackboardQueryService.fetch_entries_by_run_id``
returns into a machine-readable, byte-stable document that an independent
reader can reconcile against the ledger in one query — the retrieval leg of
ADR-159 D6 criterion C5 (reconstructability) and D9 (the evidence apparatus
must be retrievable). Pure: no I/O, no clock, no randomness. The CLI
(``core-admin workers export-run``) owns reading and writing.

Determinism contract (governor acceptance, #893, 2026-09-14):
- Entries in posting order — ``created_at`` ascending, tie-broken by ``id``.
  The query already orders that way; ``build_run_export`` re-sorts on the same
  key so the document's order does not depend on the caller.
- ``sort_keys=True``, fixed separators, ASCII-only, UTF-8, trailing newline.
- No wall-clock anywhere in the body. If an export timestamp is wanted it is
  the caller's to print beside the file, never inside it.
- Byte-identical re-export holds while the underlying rows are unchanged.
  Every entry type ``GoalExecutionWorker`` posts today is terminal at creation
  and never mutated; if a later change records non-terminal findings for a
  run, dedup upserts and claim/resolve transitions would legitimately change
  a second export — the ``reconciliation`` header exists so a reader detects
  exactly that in one query, so it is a property to know, not a defect.

Completeness gate: a run is complete when a ``goal_run.<run_id>.outcome``
entry exists — ``GoalExecutionWorker`` posts exactly one terminal outcome per
run (report, abandoned observation, or explicit-unavailability). An export
without one is a partial record that would look complete; ``build_run_export``
refuses it unless the caller opts into ``allow_partial``, in which case the
header says ``"completeness": "partial"`` so the partiality is in the file,
not in someone's memory of the console.

Omissions are a field, not a comment: what the identity predicate structurally
cannot reach is named in ``omissions`` inside the document, because the file
is what outlives the conversation (see ``_OMISSIONS``).

ADR-159 D4 adaptation accounting: this is a new module under ``src/`` and
therefore thesis-negative adaptation, recorded here as the worked pattern of
``goal_execution_worker.py`` requires (ADR-159 Note 2026-09-12(c)). It adds
retrieval of evidence that already exists; it changes nothing about what is
recorded (item 3, #873) and binds no target (item 1).

LAYER: body/services — execution-layer read facade over the ledger. No rule
evaluation, no AI, no filesystem.
"""

from __future__ import annotations

import json
from typing import Any


EXPORT_FORMAT = "core.blackboard_run_export/1"

_OMISSIONS: tuple[dict[str, str], ...] = (
    {
        "what": "worker.error entries",
        "why": (
            "Worker.start() posts subject='worker.error' with {error, worker} on an "
            "uncaught exception; the payload carries no run_id and the activity_run "
            "contextvar is already reset by then, so no predicate can correlate "
            "them to a run. A run that crashed can therefore look clean here."
        ),
        "tracked_by": "#893 sibling item 3 (what is recorded) -- #873 lineage",
    },
    {
        "what": "heartbeat entries",
        "why": (
            "GoalExecutionWorker posts no heartbeat entries; registration refreshes "
            "worker_registry.last_heartbeat only, which is not a blackboard row."
        ),
        "tracked_by": "#893 sibling item 3 (what is recorded) -- #873 lineage",
    },
    {
        "what": "core.action_results rows",
        "why": (
            "Per-action results are correlated via payload.action_results_correlation_key "
            "into core.action_results.action_metadata, a different table; this export "
            "covers the Blackboard only."
        ),
        "tracked_by": "not tracked -- candidate follow-on flag on this command",
    },
)


# ID: 9417f3cb-98d7-4226-8b11-e8a0ac8ceb82
class RunExportRefused(ValueError):
    """The run's record cannot be exported honestly; ``reason`` says why."""

    def __init__(self, reason: str, detail: str) -> None:
        super().__init__(f"{reason}: {detail}")
        self.reason = reason
        self.detail = detail


def _has_outcome(run_id: str, entries: list[dict[str, Any]]) -> bool:
    outcome_subject = f"goal_run.{run_id}.outcome"
    return any(e.get("subject") == outcome_subject for e in entries)


# ID: 05bafe4f-d5a1-4f5e-8203-ee18fffa9e08
def build_run_export(
    run_id: str,
    entries: list[dict[str, Any]],
    *,
    allow_partial: bool = False,
) -> dict[str, Any]:
    """Build the export document for *run_id* from its ledger rows.

    Raises ``RunExportRefused`` when there is nothing to reconstruct from
    (``no_entries``) or when the run has no terminal outcome entry and the
    caller did not opt into a partial record (``run_incomplete``).

    ``no_entries`` deliberately does not distinguish "no such run" from "run
    exists, recorded nothing": the Blackboard is this export's only source
    and from it those two facts are indistinguishable. The message says so.
    """
    if not entries:
        raise RunExportRefused(
            "no_entries",
            f"no blackboard entries match run_id {run_id!r} under predicate "
            f"subject LIKE 'goal_run.{run_id}.%' OR payload->>'run_id' = {run_id!r}; "
            "either the run_id is unknown or the run recorded nothing -- the "
            "Blackboard cannot tell these apart (item 3, #873 lineage)",
        )

    complete = _has_outcome(run_id, entries)
    if not complete and not allow_partial:
        raise RunExportRefused(
            "run_incomplete",
            f"no goal_run.{run_id}.outcome entry -- the run is in flight or died "
            "without recording an outcome; refusing to export a partial record "
            "that would look complete (export with allow_partial to record it "
            "stamped as partial)",
        )

    ordered = sorted(
        entries, key=lambda e: (e.get("created_at") or "", e.get("id") or "")
    )
    target_binding = _extract_target_binding(run_id, ordered)

    counts: dict[str, int] = {}
    for entry in ordered:
        counts[entry["entry_type"]] = counts.get(entry["entry_type"], 0) + 1

    return {
        "format": EXPORT_FORMAT,
        "run_id": run_id,
        "completeness": "complete" if complete else "partial",
        "identity_predicate": {
            "subject_like": f"goal_run.{run_id}.%",
            "payload_run_id": run_id,
            "sql": (
                "subject LIKE :subject_like OR payload->>'run_id' = :payload_run_id "
                "ORDER BY created_at ASC, id ASC"
            ),
        },
        "reconciliation": {
            "entry_count": len(ordered),
            "counts_by_entry_type": dict(sorted(counts.items())),
            "first_created_at": ordered[0]["created_at"],
            "last_created_at": ordered[-1]["created_at"],
            "query": (
                "SELECT entry_type, count(*), min(created_at), max(created_at) "
                "FROM core.blackboard_entries "
                "WHERE subject LIKE 'goal_run.<run_id>.%' OR payload->>'run_id' = '<run_id>' "
                "GROUP BY 1"
            ),
        },
        # #894 Unit 3: which repository the run was about -- lifted from the
        # single goal_run.<run_id>.start entry; null for a CORE-internal run.
        "target_binding": target_binding,
        "omissions": [dict(o) for o in _OMISSIONS],
        "entries": ordered,
    }


def _extract_target_binding(
    run_id: str, ordered: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Exactly one start entry may supply ``target_binding``; more than one
    start entry, or a malformed binding, refuses the export rather than
    silently choosing -- a record "about" an unknown repository is worse than
    no record (#894 Unit 3)."""
    from shared.models.target_binding import validate_binding_payload

    start_subject = f"goal_run.{run_id}.start"
    starts = [e for e in ordered if e.get("subject") == start_subject]
    if len(starts) > 1:
        raise RunExportRefused(
            "ambiguous_start",
            f"{len(starts)} entries carry subject {start_subject!r}; the run's "
            "identity (and any target_binding) cannot be attributed to one of them",
        )
    if not starts:
        return None
    payload = starts[0].get("payload") or {}
    if "target_binding" not in payload:
        return None
    binding = payload["target_binding"]
    problem = validate_binding_payload(binding)
    if problem is not None:
        raise RunExportRefused(
            "malformed_target_binding",
            f"{start_subject} carries a target_binding this export cannot vouch "
            f"for: {problem}",
        )
    return dict(binding)


# ID: 0933c736-d099-42f4-b05d-76ee4e89b9f2
def serialize_run_export(document: dict[str, Any]) -> bytes:
    """Serialize an export document to its canonical, byte-stable form."""
    text = json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return (text + "\n").encode("utf-8")
