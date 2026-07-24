# tests/cli/logic/demo/test_consequence_chain_failure_paths.py
"""ADR-155 §6.2 adversarial matrix — E05, E08-E11 (orchestration failure paths).

These exercise the *real* isolation substrate — a throwaway git repo is cloned,
seeded, fingerprinted, asserted, and cleaned/retained by the genuine
``run_consequence_chain`` orchestration — with only the Docker/child-process
boundary (``compose_up``/``compose_down``/``_container_host_port``/
``run_child_process``/``read_state_json``) monkeypatched. No Docker, no
shared infrastructure, and no fault-injection seam in production code: the
failure is expressed purely as the boundary's returned data, exactly as a real
failing run would surface it to the parent.

- E05  repeatability: three consecutive runs → distinct ids, each cleans up.
- E08  failure after seed commit: infra fails → source unchanged, workspace retained.
- E09  failure after proposal creation: failure evidence identifies the proposal.
- E10  execution failure: terminal state reported, never the success thesis.
- E11  missing consequence: a 'completed' proposal without SHAs still fails.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import cli.logic.demo.consequence_chain as cc
from cli.logic.demo.consequence_chain import run_consequence_chain
from cli.logic.demo.models import (
    ChainEvidence,
    ChainScenarioResult,
    FindingIdentity,
    ProposalIdentity,
)
from cli.logic.demo.seed import seed_relative_path
from shared.infrastructure.git_service import GitService


_FINDING_ID = "finding-x"
_PROPOSAL_ID = "proposal-x"


def _ok(returncode: int = 0) -> SimpleNamespace:
    return SimpleNamespace(returncode=returncode, stdout="", stderr="")


def _passing_scenario(run_id: str, seed_rel: str) -> ChainScenarioResult:
    proposal = ProposalIdentity(
        proposal_id=_PROPOSAL_ID,
        goal="Autonomous remediation: fix.ids",
        status="approved",
        overall_risk="safe",
        approval_required=False,
        approval_authority="risk_classification.safe_auto_approval",
        approved_by="autonomous_self_promote",
        finding_ids=[_FINDING_ID],
        action_ids=["fix.ids"],
        scope_files=[seed_rel],
    )
    return ChainScenarioResult(
        run_id=run_id,
        seed_rel_path=seed_rel,
        finding=FindingIdentity(
            entry_id=_FINDING_ID,
            subject=f"python::linkage.assign_ids::{seed_rel}",
            rule_id="linkage.assign_ids",
            file_path=seed_rel,
            status="open",
        ),
        finding_matches_count=1,
        proposal=proposal,
        chain=ChainEvidence(
            proposal=proposal,
            lifecycle_status="completed",
            execution_claimer="proposal-consumer",
            pre_execution_sha="a" * 40,
            post_execution_sha="b" * 40,
            files_changed=[seed_rel],
            findings_resolved=[_FINDING_ID],
        ),
        reaudit_clean=True,
        reaudit_matches_count=0,
        finding_final_status="resolved",
        finding_final_proposal_id=_PROPOSAL_ID,
    )


def _patch_boundary(monkeypatch, *, compose_rc: int, scenario_for):
    """Patch the Docker/child boundary. ``scenario_for(run_id, seed_rel)`` builds
    the ChainScenarioResult the (mocked) child would have written, or None when
    infra never came up (in which case ``read_state_json`` is never reached)."""

    async def _compose_up(project, compose_file, env, **kw):
        return _ok(compose_rc)

    async def _compose_down(project, compose_file, env, **kw):
        return _ok(0)

    async def _port(project, service, port):
        return "15432"

    async def _child(*a, **k):
        return None

    def _read_state(path: Path):
        # Reconstruct run identity from the state dir the parent passed.
        run_id = Path(path).parent.name
        seed_rel = seed_relative_path(run_id[:8])
        return scenario_for(run_id, seed_rel).to_dict()

    monkeypatch.setattr(cc, "compose_up", _compose_up)
    monkeypatch.setattr(cc, "compose_down", _compose_down)
    monkeypatch.setattr(cc, "_container_host_port", _port)
    monkeypatch.setattr(cc, "run_child_process", _child)
    monkeypatch.setattr(cc, "read_state_json", _read_state)


# ── E08: failure after seed commit — source unchanged, workspace retained ─────


# ID: 95d5e339-03c9-4153-908e-651aa2a57761
async def test_e08_failure_after_seed_leaves_source_unchanged_and_retains_workspace(
    source_repo: GitService, demo_state_root: Path, monkeypatch
) -> None:
    before = cc.capture_fingerprint(source_repo)
    _patch_boundary(monkeypatch, compose_rc=1, scenario_for=lambda r, s: None)

    result = await run_consequence_chain(source_repo, demo_state_root)

    assert result.ok is False
    # Workspace retained on failure (not cleaned).
    assert result.cleaned_up is False
    assert result.state_dir is not None and result.state_dir.exists()
    # The invoking source repo is byte-for-byte unchanged.
    assert cc.capture_fingerprint(source_repo).matches(before)


# ── E09: failure after proposal creation — evidence identifies the proposal ───


# ID: 49275792-dc1b-4c7d-9e1f-d7f530e9ff1c
async def test_e09_failure_after_proposal_identifies_it_in_evidence(
    source_repo: GitService, demo_state_root: Path, monkeypatch
) -> None:
    def _proposal_but_no_execution(run_id: str, seed_rel: str) -> ChainScenarioResult:
        scenario = _passing_scenario(run_id, seed_rel)
        scenario.chain = None  # execution never produced a chain
        scenario.finding_final_status = None
        scenario.finding_final_proposal_id = None
        scenario.reaudit_clean = False
        scenario.reaudit_matches_count = 1
        return scenario

    _patch_boundary(monkeypatch, compose_rc=0, scenario_for=_proposal_but_no_execution)
    result = await run_consequence_chain(source_repo, demo_state_root)

    assert result.ok is False
    # The exact proposal is preserved in the returned evidence (not lost).
    assert result.scenario is not None
    assert result.scenario.proposal is not None
    assert result.scenario.proposal.proposal_id == _PROPOSAL_ID
    assert result.cleaned_up is False and result.state_dir.exists()


# ── E10: execution failure — terminal state reported, never success ───────────


# ID: bd1ed081-44d2-4246-ab8f-34c424b495b8
async def test_e10_execution_failure_reports_terminal_state_not_success(
    source_repo: GitService, demo_state_root: Path, monkeypatch
) -> None:
    def _execution_failed(run_id: str, seed_rel: str) -> ChainScenarioResult:
        scenario = _passing_scenario(run_id, seed_rel)
        scenario.chain = ChainEvidence(
            proposal=scenario.proposal,
            lifecycle_status="failed",
            execution_claimer="proposal-consumer",
            pre_execution_sha=None,
            post_execution_sha=None,
            files_changed=[],
            findings_resolved=[],
        )
        scenario.finding_final_status = None
        scenario.finding_final_proposal_id = None
        return scenario

    _patch_boundary(monkeypatch, compose_rc=0, scenario_for=_execution_failed)
    result = await run_consequence_chain(source_repo, demo_state_root)

    assert result.ok is False
    assert result.scenario.chain.lifecycle_status == "failed"
    # The completed-execution assertion must be among the failures.
    failed = {a.name for a in result.assertions if not a.passed}
    assert "D10.6_execution_reaches_completed" in failed


# ── E11: 'completed' without a durable consequence still fails ────────────────


# ID: 4444f8b8-abd2-4aa5-a4be-fed950175756
async def test_e11_completed_without_consequence_fails(
    source_repo: GitService, demo_state_root: Path, monkeypatch
) -> None:
    def _completed_no_consequence(run_id: str, seed_rel: str) -> ChainScenarioResult:
        scenario = _passing_scenario(run_id, seed_rel)
        scenario.chain = ChainEvidence(
            proposal=scenario.proposal,
            lifecycle_status="completed",
            execution_claimer="proposal-consumer",
            pre_execution_sha=None,  # no durable consequence recorded
            post_execution_sha=None,
            files_changed=[],
            findings_resolved=[],
        )
        return scenario

    _patch_boundary(monkeypatch, compose_rc=0, scenario_for=_completed_no_consequence)
    result = await run_consequence_chain(source_repo, demo_state_root)

    assert result.ok is False
    failed = {a.name for a in result.assertions if not a.passed}
    assert "D10.7_completed_has_durable_consequence" in failed


# ── E05: three consecutive runs — distinct ids, each cleans up ────────────────


# ID: a88f5a0e-0ed9-4a17-8637-101c6170e451
async def test_e05_three_consecutive_runs_are_independent_and_clean_up(
    source_repo: GitService, demo_state_root: Path, monkeypatch
) -> None:
    _patch_boundary(monkeypatch, compose_rc=0, scenario_for=_passing_scenario)

    run_ids: list[str] = []
    state_dirs: list[Path] = []
    for _ in range(3):
        result = await run_consequence_chain(source_repo, demo_state_root)
        assert result.ok is True, [a.name for a in result.assertions if not a.passed]
        run_ids.append(result.run_id)
        state_dirs.append(result.state_dir)

    # Distinct identities.
    assert len(set(run_ids)) == 3
    # Each run cleaned up its own disposable state on success.
    assert all(sd is not None and not sd.exists() for sd in state_dirs)
    assert result.cleaned_up is True  # the final run reported its own cleanup
