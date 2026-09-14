# tests/shared/infrastructure/test_proposal_status_canonical_alignment.py

"""
Proposal-status canonical-alignment drift guard (#885 reconciliation).

Asserts that every surface declaring the Proposal lifecycle vocabulary stays
in lock-step with the governed definition:

  1. .intent/META/enums.json#/definitions/proposal_status         (canonical)
     and #/definitions/proposal_status_active                     (subset)
  2. shared.lifecycles.proposal.ProposalStatus                    (runtime enum)
  3. core.autonomous_proposals status CHECK + server_default      (ORM/DB)
  4. .intent/enforcement/contracts/{ProposalResponse,LaneProposeResponse}.json
  5. src/shared/_machinery_floor/META/enums.json                  (bundled mirror)

Read-only in every direction: the test consumes .intent/ through the
sanctioned canonical_enums accessor and never writes to it. The previous
drift this guards against was real -- `draft` outlived its retirement from
the runtime enum (#885) in the governed vocabulary, the lifecycle rule and
three contracts until reconciled by hand.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from shared.infrastructure.database.models.autonomous_proposals import (
    AutonomousProposal,
)
from shared.infrastructure.intent.canonical_enums import (
    get_enum_members,
    reload_enums_cache,
)
from shared.lifecycles.proposal import ProposalStatus


_REPO_ROOT = Path(__file__).resolve().parents[3]
_CONTRACTS = _REPO_ROOT / ".intent" / "enforcement" / "contracts"
_FLOOR_ENUMS = (
    _REPO_ROOT / "src" / "shared" / "_machinery_floor" / "META" / "enums.json"
)


def setup_function(_func) -> None:
    """Force a fresh read of enums.json for every test."""
    reload_enums_cache()


def _runtime_values() -> frozenset[str]:
    return frozenset(s.value for s in ProposalStatus)


def _contract_status_enum(name: str) -> frozenset[str]:
    doc = json.loads((_CONTRACTS / name).read_text(encoding="utf-8"))
    return frozenset(doc["properties"]["status"]["enum"])


def test_runtime_enum_matches_governed_proposal_status() -> None:
    """ProposalStatus values == enums.json proposal_status, both directions."""
    governed = get_enum_members("proposal_status")
    assert _runtime_values() == governed, (
        f"runtime ProposalStatus {sorted(_runtime_values())} != governed "
        f"proposal_status {sorted(governed)}"
    )


def test_governed_vocabulary_has_no_draft_and_single_pre_approval_state() -> None:
    """#885: `draft` is retired; `pending` is the only pre-approval state."""
    governed = get_enum_members("proposal_status")
    assert "draft" not in governed
    post_approval = {
        "approved",
        "executing",
        "finalizing",
        "completed",
        "failed",
        "rejected",
    }
    assert governed - post_approval == {"pending"}


def test_active_subset_is_within_governed_and_has_no_draft() -> None:
    """proposal_status_active ⊂ proposal_status; the dedup-blocking set has
    no retired member."""
    governed = get_enum_members("proposal_status")
    active = get_enum_members("proposal_status_active")
    assert active <= governed, sorted(active - governed)
    assert "draft" not in active
    assert "pending" in active and "approved" in active


def test_orm_check_constraint_and_default_match_governed() -> None:
    """DB vocabulary == governed vocabulary; default row state is `pending`."""
    governed = get_enum_members("proposal_status")
    check = next(
        c
        for c in AutonomousProposal.__table__.constraints
        if getattr(c, "name", None) == "autonomous_proposals_status_check"
    )
    db_vocab = frozenset(re.findall(r"'([a-z_]+)'", str(check.sqltext)))
    assert db_vocab == governed, (
        f"ORM CHECK {sorted(db_vocab)} != governed {sorted(governed)}"
    )
    assert AutonomousProposal.__table__.c.status.server_default.arg == "pending"


def test_contracts_declare_only_governed_statuses() -> None:
    """ProposalResponse exposes the full governed set; LaneProposeResponse's
    initial-status subset lies within it and has no retired member."""
    governed = get_enum_members("proposal_status")
    assert _contract_status_enum("ProposalResponse.json") == governed
    lane = _contract_status_enum("LaneProposeResponse.json")
    assert lane <= governed, sorted(lane - governed)
    assert "draft" not in lane
    assert "pending" in lane


def test_machinery_floor_mirror_matches_governed_proposal_status() -> None:
    """The bundled floor copy (ADR-108 D3) is kept at parity by lockstep edit
    in the same commit; this catches the half-done case for the Proposal
    lifecycle vocabulary specifically."""
    floor = json.loads(_FLOOR_ENUMS.read_text(encoding="utf-8"))["definitions"]
    assert frozenset(floor["proposal_status"]["enum"]) == get_enum_members(
        "proposal_status"
    )
    assert frozenset(floor["proposal_status_active"]["enum"]) == get_enum_members(
        "proposal_status_active"
    )
