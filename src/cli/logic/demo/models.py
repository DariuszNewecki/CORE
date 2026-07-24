# src/cli/logic/demo/models.py
"""
Typed records for the isolated consequence-chain demo substrate (ADR-155).

Phase 1 populates ``RunIdentity`` and ``IsolationFingerprint`` in full.
``AssertionResult``/``PhaseResult`` are the shell Phase 2's chain-scenario
assertions (D10's full 15-assertion model) and Phase 3's CLI evidence
rendering (D12) both build on — defined here so later phases extend this
shell rather than redefining the wire types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
# ID: b41c9665-8040-4b81-98d9-609db13faeae
class RunIdentity:
    """Opaque identity for one demo run (ADR-155 D3).

    ``run_id`` is the only handle callers pass between substrate steps;
    every other path is derived from it plus ``state_dir``.
    """

    run_id: str
    state_dir: Path
    marker_path: Path
    clone_dir: Path


@dataclass(frozen=True)
# ID: a25cb366-3f7a-42f1-b661-c645449082e2
class IsolationFingerprint:
    """Byte-identity snapshot of the invoking repo (ADR-155 D2/D10 assertion 15).

    ``untracked_files`` maps each pre-existing untracked path to its content
    hash, so a before/after comparison can prove not just that tracked
    HEAD/index are unchanged but that no pre-existing untracked byte was
    touched either.
    """

    head_sha: str
    index_tree_sha: str
    tracked_tree_sha: str
    untracked_files: dict[str, str]

    # ID: 3d4b3fb2-8fe8-41af-b035-b2f6987a89a8
    def matches(self, other: IsolationFingerprint) -> bool:
        """Return True if two fingerprints are byte-identical."""
        return (
            self.head_sha == other.head_sha
            and self.index_tree_sha == other.index_tree_sha
            and self.tracked_tree_sha == other.tracked_tree_sha
            and self.untracked_files == other.untracked_files
        )


@dataclass
# ID: 20273825-c2bc-4eae-a077-f549d55e9f49
class AssertionResult:
    """One named pass/fail check from the ADR-155 D10 fail-closed assertion model.

    Phase 1 populates only isolation-scoped assertions (the Phase1-Map §
    "Phase 1 test plan" subset); the full chain-scenario assertion set is
    Phase 2's responsibility.
    """

    name: str
    passed: bool
    detail: str = ""


@dataclass
# ID: 32823975-63ac-4914-a048-37ab3a77ec95
class PhaseResult:
    """Outcome shell for one substrate run (clone, compose up/down, cleanup).

    Phase 1 populates ``run_id``/``ok``/``assertions``. Phase 2 adds the
    chain-scenario evidence fields (finding, proposal, consequence, etc.) on
    top of this shell rather than replacing it; Phase 3's CLI renders D12
    evidence from whatever this shell has accumulated by the end of a run.

    The evidence fields carry the *exact* records the real chain produced —
    ``scenario`` is the unmodified ``ChainScenarioResult`` handed back by the
    child process. Phase 3's D12 renderer reads from these fields directly and
    never re-derives a fact from a separate query or "latest" selection.
    ``state_dir`` is the retained-workspace path an operator inspects (and
    passes to ``core-admin demo cleanup``) when a run fails or is kept.
    """

    run_id: str
    ok: bool
    assertions: list[AssertionResult] = field(default_factory=list)
    assessed_commit: str | None = None
    state_dir: Path | None = None
    cleaned_up: bool = False
    scenario: ChainScenarioResult | None = None


@dataclass(frozen=True)
# ID: 2a26ff45-7f94-4187-ac4c-78f04faa05db
class FindingIdentity:
    """Exact identity of the seeded finding (ADR-155 D8).

    Resolved by an exact-subject query against the real blackboard — never
    "latest" or a count-insensitive match. ``rule_id`` and ``file_path`` are
    read back from the payload, not re-derived, so a mismatch there is
    itself detectable rather than assumed away.
    """

    entry_id: str
    subject: str
    rule_id: str
    file_path: str
    status: str


@dataclass(frozen=True)
# ID: eb24799a-618d-403d-a1a8-04903f55eee7
class ProposalIdentity:
    """Exact identity and declared state of the linked proposal (ADR-155 D8/D9).

    ``finding_ids`` is read from ``constitutional_constraints.finding_ids`` —
    the real bidirectional linkage field — not inferred from ordering or
    goal text.
    """

    proposal_id: str
    goal: str
    status: str
    overall_risk: str
    approval_required: bool
    approval_authority: str | None
    approved_by: str | None
    finding_ids: list[str]
    action_ids: list[str]
    scope_files: list[str]


@dataclass(frozen=True)
# ID: 2a73e481-6f6b-43d8-8120-967880cded36
class ChainEvidence:
    """Facts read back from ``GET /v1/proposals/{id}/chain`` (ADR-155 D6/D12).

    Every D10 assertion about execution/consequence reads from exactly this
    response — never re-derived from a separate query, per D6's "direct SQL
    and latest-selection are prohibited."
    """

    proposal: ProposalIdentity
    lifecycle_status: str
    execution_claimer: str | None
    pre_execution_sha: str | None
    post_execution_sha: str | None
    files_changed: list[str]
    findings_resolved: list[str]


@dataclass
# ID: cecf9a33-1bd8-4f41-9587-e023b0374a55
class ChainScenarioResult:
    """Full Phase 2 scenario outcome, produced by the child scenario process
    (``scenario_runner.py``) and handed back to the parent orchestrator via
    the run's state-dir JSON (``isolation.write_state_json``).

    Combines the D8 finding/proposal identity, D6 chain evidence, and the
    re-audit closure check (D10 assertion 13) into one record. The parent —
    which alone holds the D7 seed proofs and the invoking-repo/.intent
    fingerprints — combines this with its own facts to evaluate all 15 D10
    assertions; this record is deliberately not itself a verdict.
    """

    run_id: str
    seed_rel_path: str
    finding: FindingIdentity | None
    finding_matches_count: int
    proposal: ProposalIdentity | None
    chain: ChainEvidence | None
    reaudit_clean: bool
    reaudit_matches_count: int
    finding_final_status: str | None = None
    finding_final_proposal_id: str | None = None
    error: str | None = None

    # ID: 2cdbfe6a-8242-42a9-925b-42072332ec69
    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dict (all leaves are already JSON-safe)."""
        from dataclasses import asdict

        return asdict(self)

    @classmethod
    # ID: cda17549-6f8c-4a3c-afef-7963a7a98256
    def from_dict(cls, data: dict[str, Any]) -> ChainScenarioResult:
        """Reconstruct from the dict produced by ``to_dict``."""
        finding_data = data.get("finding")
        proposal_data = data.get("proposal")
        chain_data = data.get("chain")

        finding = FindingIdentity(**finding_data) if finding_data else None
        proposal = ProposalIdentity(**proposal_data) if proposal_data else None
        chain = None
        if chain_data:
            chain_proposal_data = chain_data["proposal"]
            chain = ChainEvidence(
                proposal=ProposalIdentity(**chain_proposal_data),
                lifecycle_status=chain_data["lifecycle_status"],
                execution_claimer=chain_data["execution_claimer"],
                pre_execution_sha=chain_data["pre_execution_sha"],
                post_execution_sha=chain_data["post_execution_sha"],
                files_changed=chain_data["files_changed"],
                findings_resolved=chain_data["findings_resolved"],
            )

        return cls(
            run_id=data["run_id"],
            seed_rel_path=data["seed_rel_path"],
            finding=finding,
            finding_matches_count=data["finding_matches_count"],
            proposal=proposal,
            chain=chain,
            reaudit_clean=data["reaudit_clean"],
            reaudit_matches_count=data["reaudit_matches_count"],
            finding_final_status=data.get("finding_final_status"),
            finding_final_proposal_id=data.get("finding_final_proposal_id"),
            error=data.get("error"),
        )
