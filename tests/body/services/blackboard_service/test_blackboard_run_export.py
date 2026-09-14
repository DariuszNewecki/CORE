# tests/body/services/blackboard_service/test_blackboard_run_export.py
"""Determinism + honesty contract of the run export builder (#893).

Pure-function tests over canned rows shaped like
``BlackboardQueryService.fetch_entries_by_run_id`` output. The two governor
acceptance criteria (byte-identical re-export; header counts reconcile with
the entries in the same file) plus the three review amendments (completeness
gate, omissions as a field, no wall-clock in the body).
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from body.services.blackboard_service.blackboard_run_export import (
    EXPORT_FORMAT,
    RunExportRefused,
    build_run_export,
    serialize_run_export,
)


RID = "11111111-2222-4333-8444-555555555555"


def _row(
    entry_id: str,
    subject: str,
    created_at: str,
    *,
    entry_type: str = "report",
    status: str = "resolved",
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": entry_id,
        "worker_uuid": "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
        "entry_type": entry_type,
        "phase": "execution",
        "status": status,
        "subject": subject,
        "payload": payload if payload is not None else {"run_id": RID},
        "first_payload": None,
        "resolution_mechanism": None,
        "claimed_by": None,
        "claimed_at": None,
        "resolved_at": None,
        "created_at": created_at,
        "updated_at": created_at,
        "last_seen_at": created_at,
        "occurrence_count": 1,
        "orphan_release_count": 0,
    }


def _complete_run() -> list[dict[str, Any]]:
    return [
        _row("e1", f"goal_run.{RID}.start", "2026-09-13T11:24:36.969586+00:00"),
        _row(
            "e2",
            f"goal_run.{RID}.outcome",
            "2026-09-13T11:24:38.459744+00:00",
            payload={"run_id": RID, "ok": True},
        ),
    ]


# ── Criterion 1: byte-identical re-export ─────────────────────────────────────


def test_export_twice_yields_identical_bytes() -> None:
    a = serialize_run_export(build_run_export(RID, _complete_run()))
    b = serialize_run_export(build_run_export(RID, _complete_run()))
    assert a == b


def test_serialization_is_canonical() -> None:
    raw = serialize_run_export(build_run_export(RID, _complete_run()))
    assert raw.endswith(b"\n")
    assert raw.count(b"\n") == 1  # single line, fixed separators
    text = raw.decode("utf-8")
    assert text.isascii()
    doc = json.loads(text)
    assert list(doc.keys()) == sorted(doc.keys())  # sort_keys at the top level
    assert doc["format"] == EXPORT_FORMAT


def test_body_carries_no_wall_clock() -> None:
    doc = build_run_export(RID, _complete_run())
    flat = json.dumps(doc)
    assert "exported_at" not in flat
    # Every timestamp in the file is one the ledger already held.
    for key in ("first_created_at", "last_created_at"):
        assert doc["reconciliation"][key] in {e["created_at"] for e in _complete_run()}


def test_order_is_created_at_then_id_regardless_of_input_order() -> None:
    same_ts = "2026-09-13T11:24:37.000000+00:00"
    rows = [
        _row("zz", f"goal_run.{RID}.outcome", same_ts),
        _row("aa", "goal_run.other.note", same_ts),
        _row("mm", f"goal_run.{RID}.start", "2026-09-13T11:24:36.000000+00:00"),
    ]
    doc = build_run_export(RID, rows)
    assert [e["id"] for e in doc["entries"]] == ["mm", "aa", "zz"]


# ── Criterion 2: the header reconciles against the entries in the same file ──


def test_header_counts_equal_entry_counts() -> None:
    rows = [
        *_complete_run(),
        _row(
            "e3",
            f"goal_run.{RID}.note",
            "2026-09-13T11:24:37.000000+00:00",
            entry_type="finding",
            status="resolved",
        ),
    ]
    doc = build_run_export(RID, rows)
    recon = doc["reconciliation"]
    assert recon["entry_count"] == len(doc["entries"])
    by_type: dict[str, int] = {}
    for e in doc["entries"]:
        by_type[e["entry_type"]] = by_type.get(e["entry_type"], 0) + 1
    assert recon["counts_by_entry_type"] == by_type
    assert recon["first_created_at"] == doc["entries"][0]["created_at"]
    assert recon["last_created_at"] == doc["entries"][-1]["created_at"]
    assert recon["query"].startswith("SELECT entry_type, count(*)")


def test_identity_predicate_is_stated_in_the_file() -> None:
    doc = build_run_export(RID, _complete_run())
    pred = doc["identity_predicate"]
    assert pred["subject_like"] == f"goal_run.{RID}.%"
    assert pred["payload_run_id"] == RID
    assert "payload->>'run_id'" in pred["sql"]


# ── Amendment 2: omissions are a field, not a comment ────────────────────────


def test_omissions_name_what_the_predicate_cannot_reach() -> None:
    doc = build_run_export(RID, _complete_run())
    whats = {o["what"] for o in doc["omissions"]}
    assert "worker.error entries" in whats
    assert "heartbeat entries" in whats
    assert "core.action_results rows" in whats
    for o in doc["omissions"]:
        assert o["why"] and o["tracked_by"]


# ── Amendment 1: completeness gate ───────────────────────────────────────────


def test_complete_run_is_stamped_complete() -> None:
    assert build_run_export(RID, _complete_run())["completeness"] == "complete"


def test_run_without_outcome_is_refused_by_default() -> None:
    rows = _complete_run()[:1]  # start only
    with pytest.raises(RunExportRefused) as exc:
        build_run_export(RID, rows)
    assert exc.value.reason == "run_incomplete"
    assert f"goal_run.{RID}.outcome" in exc.value.detail


def test_run_without_outcome_exports_stamped_partial_on_opt_in() -> None:
    rows = _complete_run()[:1]
    doc = build_run_export(RID, rows, allow_partial=True)
    assert doc["completeness"] == "partial"
    assert doc["reconciliation"]["entry_count"] == 1


def test_no_entries_is_refused_and_says_the_two_facts_are_indistinguishable() -> None:
    with pytest.raises(RunExportRefused) as exc:
        build_run_export(RID, [])
    assert exc.value.reason == "no_entries"
    assert "cannot tell these apart" in exc.value.detail
    # allow_partial does not turn nothing into something
    with pytest.raises(RunExportRefused):
        build_run_export(RID, [], allow_partial=True)
