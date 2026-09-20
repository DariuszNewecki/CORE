# tests/will/workers/test_violation_remediator_inherited_cap.py
"""ViolationRemediatorWorker inherits the ADR-104 D9 remediation-attempt
count before minting a proposal (#901, mapped-rule path).

The audit sensor dedups against every status except ``resolved`` and
``abandoned`` (#263), so a violation abandoned at the cap comes back as a
fresh row next cycle with a zero counter. The unmapped path
(ViolationExecutorWorker) and TestRemediatorWorker already read the cap
from the abandoned lineage before doing work; the mapped path did not, so
after abandon-at-cap it minted the next proposal for the same file and
rule as if nothing had happened. These tests pin the collaborator
``abandon_capped_findings`` (subject-scoped lookup, fail-soft to 0,
abandon with the inherited count stamped) and the run() wiring: a group
whose every finding is at the cap mints nothing; a partially capped group
mints a proposal for the survivors only.

Hermetic: blackboard service is a stub, proposal creation is mocked.
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from will.autonomy.violation_remediator_blackboard import abandon_capped_findings
from will.workers.violation_remediator import ViolationRemediatorWorker


_RULE = "architecture.channels.logic_no_terminal_rendering"
_REF_ID = "fix.logging"


def _finding(file_path: str) -> dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "subject": f"python::{_RULE}::{file_path}",
        "payload": {"file_path": file_path, "rule": _RULE, "check_id": _RULE},
    }


class _StubBlackboard:
    """Counts by subject; records every abandon call."""

    def __init__(self, counts: dict[str, int], *, raise_for: str | None = None):
        self._counts = counts
        self._raise_for = raise_for
        self.abandoned: list[tuple[list[str], int]] = []

    async def query_max_attempt_count_by_subject(self, subject: str) -> int:
        if subject == self._raise_for:
            raise RuntimeError("lookup outage")
        return self._counts.get(subject, 0)

    async def abandon_remediation_capped_findings(
        self, entry_ids: list[str], count: int
    ) -> list[str]:
        self.abandoned.append((entry_ids, count))
        return list(entry_ids)


# ---------------------------------------------------------------------------
# Collaborator
# ---------------------------------------------------------------------------


# ID: 1295b812-d697-44d4-a9e5-cf1af400787d
async def test_abandons_only_findings_at_or_over_the_cap() -> None:
    at_cap, under, over = _finding("a.py"), _finding("b.py"), _finding("c.py")
    svc = _StubBlackboard(
        {at_cap["subject"]: 3, under["subject"]: 2, over["subject"]: 7}
    )

    abandoned = await abandon_capped_findings(svc, [at_cap, under, over], cap_n=3)

    assert abandoned == [at_cap["id"], over["id"]]
    # The inherited count is stamped, so the lineage keeps climbing.
    assert svc.abandoned == [([at_cap["id"]], 3), ([over["id"]], 7)]


# ID: 3670b314-601a-43f3-8186-8cbef762ba70
async def test_lookup_outage_reads_as_zero_and_keeps_the_finding() -> None:
    """Fail-soft toward retry: a service hiccup must never abandon."""
    f = _finding("a.py")
    svc = _StubBlackboard({f["subject"]: 99}, raise_for=f["subject"])

    assert await abandon_capped_findings(svc, [f], cap_n=3) == []
    assert svc.abandoned == []


# ---------------------------------------------------------------------------
# Worker wiring
# ---------------------------------------------------------------------------


async def _run(
    findings: list[dict[str, Any]], svc: _StubBlackboard
) -> tuple[dict[str, Any], AsyncMock]:
    worker = object.__new__(ViolationRemediatorWorker)
    worker._declaration = {}
    worker._max_interval = 300
    worker._worker_uuid = uuid.uuid4()
    worker._ctx = MagicMock()
    worker._core_context = MagicMock()
    worker.declaration_name = "violation_remediator"
    worker._load_open_findings = AsyncMock(return_value=findings)
    worker._get_remediation_map = MagicMock(
        return_value={
            _RULE: {"ref_id": _REF_ID, "ref_kind": "action", "status": "ACTIVE"}
        }
    )
    worker._get_active_proposal_id_by_action_file = AsyncMock(return_value={})
    worker._check_circuit_breaker = AsyncMock(return_value=(0, None, None, None))
    worker._is_file_committed = MagicMock(return_value=True)
    worker._blackboard_service = AsyncMock(return_value=svc)
    worker._release_unmappable = AsyncMock(return_value=0)
    worker._mark_delegated = AsyncMock(return_value=0)
    worker._release_entries = AsyncMock(return_value=0)
    create = AsyncMock(
        return_value=MagicMock(
            proposal_id="pid-new", deferred_count=1, auto_approved=True
        )
    )
    worker._create_proposal = create
    worker.post_report = AsyncMock()
    worker.post_heartbeat = AsyncMock()
    worker.post_observation = AsyncMock()

    config = MagicMock()
    config.blackboard.remediation_cap_n = 3
    with (
        patch("will.workers.violation_remediator.load_vocabulary_projection") as vp,
        patch("will.workers.violation_remediator.load_circuit_breaker_config") as cb,
        patch(
            "will.workers.violation_remediator.load_operational_config",
            return_value=config,
        ),
    ):
        vp.return_value = MagicMock()
        cb.return_value = MagicMock(threshold_n=5)
        await worker.run()
    return worker.post_report.call_args.kwargs["payload"], create


# ID: 4e3bddcc-9d3b-4e7b-9f58-5b65dbc40549
async def test_fully_capped_group_mints_no_proposal() -> None:
    f = _finding("src/shared/infrastructure/repositories/db/ledger_seed.py")
    svc = _StubBlackboard({f["subject"]: 3})

    payload, create = await _run([f], svc)

    create.assert_not_awaited()
    assert svc.abandoned == [([f["id"]], 3)]
    assert payload["proposals_created"] == 0
    assert payload["proposals_capped"] == 1
    assert payload["entries_capped"] == 1
    assert payload["capped_actions"] == [f"{_REF_ID}::{f['payload']['file_path']}"]


# ID: 28d699b6-8d9f-4ffd-92cb-e147c03cc104
async def test_partially_capped_group_mints_for_the_survivors_only() -> None:
    """Two findings share the (ref_id, file_path) group key here only
    because the test pins them to one file; the capped one is abandoned,
    the other still reaches _create_proposal alone."""
    capped, fresh = _finding("x.py"), _finding("x.py")
    svc = _StubBlackboard({capped["subject"]: 3})
    # Same subject for both (same rule, same file) would cap both; give the
    # survivor its own subject so only lineage, not grouping, decides.
    fresh["subject"] = "python::other.rule::x.py"

    payload, create = await _run([capped, fresh], svc)

    create.assert_awaited_once()
    assert create.await_args.args[2] == [fresh]
    assert payload["proposals_created"] == 1
    assert payload["proposals_capped"] == 0
    assert payload["entries_capped"] == 1


# ID: 6ce7cfba-77db-430f-9196-d8d28b68f7ec
async def test_uncapped_findings_proceed_unchanged() -> None:
    f = _finding("y.py")
    svc = _StubBlackboard({})

    payload, create = await _run([f], svc)

    create.assert_awaited_once()
    assert svc.abandoned == []
    assert payload["entries_capped"] == 0
    assert payload["proposals_capped"] == 0
