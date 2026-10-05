"""StateSensor (ADR-169 D1/D2/D3, ADR-030).

Acceptance checks 1-3 at the worker's boundary:
- an uncommitted .intent/ edit is named by a finding within one cycle;
- committing it (relationship MATCH) resolves the finding;
- a daemon running stale code posts governance::stale_daemon, escalates once
  after the window, and resolves after restart.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from body.services.state_ledger_service import StateObservation
from shared.infrastructure.code_identity import CodeDrift
from shared.infrastructure.intent.law_state import LawState
from will.workers.state_sensor import (
    StateSensor,
    escalation_due,
    law_drift_subjects,
)


_DRIFT = LawState(
    relationship="DRIFT",
    head_sha="c" * 40,
    record_digest="r",
    evaluated_digest="e",
    drift_paths=[".intent/rules/a.json", ".intent/workers/b.yaml"],
)
_MATCH = LawState(
    relationship="MATCH", head_sha="c" * 40, record_digest="r", evaluated_digest="r"
)
_CODE_MATCH = CodeDrift(state="match", loaded_identity="a", disk_identity="a")
_CODE_STALE = CodeDrift(state="stale", loaded_identity="a", disk_identity="b")


# -- pure helpers --------------------------------------------------------------


def test_match_wants_no_findings() -> None:
    assert law_drift_subjects(_MATCH) == {}


def test_drift_wants_one_finding_per_path() -> None:
    assert law_drift_subjects(_DRIFT) == {
        "governance::law_drift::.intent/rules/a.json": ".intent/rules/a.json",
        "governance::law_drift::.intent/workers/b.yaml": ".intent/workers/b.yaml",
    }


def test_unknown_law_is_one_finding_never_silence() -> None:
    state = LawState(relationship="UNKNOWN", reason="not a git work tree")
    assert list(law_drift_subjects(state)) == ["governance::law_drift::(unknown)"]


def test_escalation_waits_for_the_window() -> None:
    now = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)
    assert not escalation_due((now - timedelta(minutes=29)).isoformat(), 30, now)
    assert escalation_due((now - timedelta(minutes=30)).isoformat(), 30, now)


@pytest.mark.parametrize("stamp", [None, "", "not-a-time"])
def test_unreadable_timestamp_escalates(stamp: str | None) -> None:
    assert escalation_due(stamp, 30, datetime.now(UTC))


# -- run() ---------------------------------------------------------------------


class _Blackboard:
    """In-memory open findings, keyed by subject."""

    def __init__(self, open_findings: dict[str, dict[str, Any]] | None = None):
        self.open: dict[str, dict[str, Any]] = dict(open_findings or {})
        self.resolved: list[str] = []

    async def fetch_open_findings(self, prefix: str, limit: int) -> list[dict]:
        stem = prefix.rstrip("%")
        return [{"subject": s, **f} for s, f in self.open.items() if s.startswith(stem)]

    async def resolve_entries(self, ids: list[str]) -> int:
        for subject, finding in list(self.open.items()):
            if finding["id"] in ids:
                self.resolved.append(subject)
                del self.open[subject]
        return len(ids)


def _sensor() -> tuple[StateSensor, MagicMock]:
    sensor = StateSensor.__new__(StateSensor)
    sensor._declaration = {"identity": {"class": "sensing"}}
    sensor._worker_name = "State Sensor"
    sensor._cycle_post_count = 0
    sensor._core_context = MagicMock()
    sensor._core_context.git_service.repo_path = Path("/repo")
    publisher = MagicMock()
    publisher.post_heartbeat = AsyncMock(return_value=uuid.uuid4())
    publisher.post_report = AsyncMock(return_value=uuid.uuid4())
    publisher.post_finding = AsyncMock(return_value=uuid.uuid4())
    sensor._blackboard = publisher
    return sensor, publisher


async def _cycle(
    law: LawState,
    code: CodeDrift,
    blackboard: _Blackboard,
    *,
    escalation_minutes: int = 30,
) -> tuple[MagicMock, AsyncMock]:
    sensor, publisher = _sensor()
    observation = StateObservation(
        trigger="cycle", repo_root="/repo", law_state=law, head_sha=law.head_sha
    )
    record = AsyncMock(return_value=True)
    with (
        patch(
            "body.services.state_ledger_service.observe_state",
            return_value=observation,
        ),
        patch(
            "body.services.state_ledger_service.StateLedgerService.record_if_changed",
            record,
        ),
        patch(
            "body.services.service_registry.service_registry.get_blackboard_service",
            AsyncMock(return_value=blackboard),
        ),
        patch("will.workers.state_sensor.code_drift", return_value=code),
        patch.object(
            StateSensor, "_escalation_minutes", return_value=escalation_minutes
        ),
    ):
        await sensor.run()
    return publisher, record


def _subjects(publisher: MagicMock) -> list[str]:
    return [c.args[0] for c in publisher.post_finding.await_args_list]


async def test_uncommitted_law_edit_is_named_within_one_cycle() -> None:
    publisher, record = await _cycle(_DRIFT, _CODE_MATCH, _Blackboard())

    assert _subjects(publisher) == [
        "governance::law_drift::.intent/rules/a.json",
        "governance::law_drift::.intent/workers/b.yaml",
    ]
    call = publisher.post_finding.await_args_list[0]
    assert call.kwargs["resolution_mechanism"] == "self_resolve"
    assert call.args[1]["path"] == ".intent/rules/a.json"
    assert call.args[1]["head_sha"] == "c" * 40
    record.assert_awaited_once()
    report = publisher.post_report.await_args.args[1]
    assert report["law_relationship"] == "DRIFT"
    assert report["law_drift_posted"] == 2


async def test_open_drift_finding_is_not_reposted() -> None:
    bb = _Blackboard(
        {
            "governance::law_drift::.intent/rules/a.json": {"id": "1", "payload": {}},
            "governance::law_drift::.intent/workers/b.yaml": {"id": "2", "payload": {}},
        }
    )
    publisher, _ = await _cycle(_DRIFT, _CODE_MATCH, bb)
    assert _subjects(publisher) == []


async def test_committing_the_law_resolves_the_finding() -> None:
    bb = _Blackboard(
        {"governance::law_drift::.intent/rules/a.json": {"id": "1", "payload": {}}}
    )
    publisher, _ = await _cycle(_MATCH, _CODE_MATCH, bb)
    assert bb.resolved == ["governance::law_drift::.intent/rules/a.json"]
    assert _subjects(publisher) == []


async def test_stale_daemon_is_posted_once_with_its_identities() -> None:
    publisher, _ = await _cycle(_MATCH, _CODE_STALE, _Blackboard())

    assert _subjects(publisher) == ["governance::stale_daemon::core-daemon"]
    payload = publisher.post_finding.await_args.args[1]
    assert payload["rule"] == "governance.stale_daemon"
    assert payload["autonomous_execution"] == "suspended"
    assert payload["loaded_code_identity"] == "a"
    assert payload["disk_code_identity"] == "b"
    assert payload["first_observed_at"]


async def test_unattended_stale_daemon_escalates_once() -> None:
    old = (datetime.now(UTC) - timedelta(minutes=45)).isoformat()
    bb = _Blackboard(
        {
            "governance::stale_daemon::core-daemon": {
                "id": "s",
                "payload": {"first_observed_at": old},
            }
        }
    )
    publisher, _ = await _cycle(_MATCH, _CODE_STALE, bb)
    assert _subjects(publisher) == ["governance::stale_daemon_escalated::core-daemon"]
    payload = publisher.post_finding.await_args.args[1]
    assert payload["priority"] == "elevated"
    assert payload["first_observed_at"] == old

    bb.open["governance::stale_daemon_escalated::core-daemon"] = {
        "id": "e",
        "payload": {},
    }
    publisher, _ = await _cycle(_MATCH, _CODE_STALE, bb)
    assert _subjects(publisher) == []


async def test_stale_daemon_within_window_does_not_escalate() -> None:
    recent = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
    bb = _Blackboard(
        {
            "governance::stale_daemon::core-daemon": {
                "id": "s",
                "payload": {"first_observed_at": recent},
            }
        }
    )
    publisher, _ = await _cycle(_MATCH, _CODE_STALE, bb)
    assert _subjects(publisher) == []


async def test_restart_resolves_stale_and_escalated_findings() -> None:
    bb = _Blackboard(
        {
            "governance::stale_daemon::core-daemon": {"id": "s", "payload": {}},
            "governance::stale_daemon_escalated::core-daemon": {
                "id": "e",
                "payload": {},
            },
        }
    )
    publisher, _ = await _cycle(_MATCH, _CODE_MATCH, bb)
    assert sorted(bb.resolved) == [
        "governance::stale_daemon::core-daemon",
        "governance::stale_daemon_escalated::core-daemon",
    ]
    assert _subjects(publisher) == []
