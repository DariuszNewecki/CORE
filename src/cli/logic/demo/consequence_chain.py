# src/cli/logic/demo/consequence_chain.py
"""
Isolated consequence-chain demo — Phase 2 parent orchestration (ADR-155).

Runs in the *parent* process (the invoking checkout's own environment).
Composes the Phase 1 isolation substrate with the Phase 2 chain scenario
(``scenario_runner.py``, run in a child process per D5) without
implementing a domain substitute for any of it (D6): this module's own job
is orchestration and the D10 fail-closed assertion model, never a
demo-only audit/proposal/execution/evidence path.

Sequence: seed (D7, parent-side proofs) -> disposable infra up -> child
process runs the real chain scenario -> disposable infra down -> evaluate
all 15 D10 assertions against the parent's own fingerprint/hash facts
combined with the child's ``ChainScenarioResult`` -> cleanup.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from body.infrastructure.storage.file_handler import FileHandler
from cli.logic.demo.isolation import (
    capture_fingerprint,
    cleanup_run,
    compose_down,
    compose_up,
    create_isolated_clone,
    generate_run_identity,
    hash_directory,
    prove_clone_isolation,
    read_state_json,
)
from cli.logic.demo.models import AssertionResult, ChainScenarioResult, PhaseResult
from cli.logic.demo.seed import seed_relative_path, write_and_commit_seed
from shared.infrastructure.git_service import GitService
from shared.logger import getLogger
from shared.utils.subprocess_utils import run_child_process, run_command_async


logger = getLogger(__name__)

_TARGET_RULE_ID = "linkage.assign_ids"
_SAFE_RISK = "safe"
_SAFE_AUTO_APPROVAL_AUTHORITY = "risk_classification.safe_auto_approval"
_SAFE_AUTO_APPROVAL_APPROVER = "autonomous_self_promote"
_EXPECTED_ACTION_ID = "fix.ids"
_COMPLETED_STATUS = "completed"
_RESOLVED_STATUS = "resolved"


async def _container_host_port(project_name: str, service: str, container_port: int) -> str:
    """Return the loopback host port Docker published for a compose service."""
    container = f"{project_name}-{service}-1"
    result = await run_command_async(["docker", "port", container, str(container_port)])
    # stdout e.g. "127.0.0.1:32783"
    return result.stdout.strip().rsplit(":", 1)[-1]


def _write_child_env(clone_repo_path: Path, pg_port: str, qdrant_port: str) -> None:
    """Write the clone's own `.env` (D5) — isolated config, LLM disabled.

    Routes through FileHandler: `.env` at repo root falls to the
    `repo-source` default classification (no explicit target-class prefix
    matches it), but the `write()` method's syntax-check/ID-anchor-injection
    transforms only apply to paths ending `.py` — a plain write for this
    non-Python file.
    """
    content = (
        "CORE_ENV=development\n"
        "LLM_ENABLED=False\n"
        f"DATABASE_URL=postgresql+asyncpg://core_demo:core_demo@127.0.0.1:{pg_port}/core_demo\n"
        f"QDRANT_URL=http://127.0.0.1:{qdrant_port}\n"
        "CORE_STRICT_MODE=False\n"
    )
    FileHandler(str(clone_repo_path)).write_runtime_text(".env", content)


def _evaluate_assertions(
    *,
    infra_healthy: bool,
    seed_commit_files: list[str] | None,
    seed_rel_path: str,
    intent_hash_before: str,
    intent_hash_after: str,
    result: ChainScenarioResult,
    source_fingerprint_matches: bool,
) -> list[AssertionResult]:
    """Evaluate the ADR-155 D10 fail-closed assertion model (15 checks).

    Every assertion is recorded, passing or failing — none is skipped, and
    a missing precondition (e.g. no finding resolved) fails every
    assertion that depends on it rather than being silently omitted.
    """
    assertions: list[AssertionResult] = []

    def _add(name: str, passed: bool, detail: str = "") -> None:
        assertions.append(AssertionResult(name=name, passed=bool(passed), detail=detail))

    _add("D10.1_infra_healthy", infra_healthy)
    _add(
        "D10.2_seed_commit_contains_only_seed_file",
        seed_commit_files == [seed_rel_path],
        detail=str(seed_commit_files),
    )

    finding = result.finding
    _add(
        "D10.3_exactly_expected_finding",
        finding is not None
        and result.finding_matches_count == 1
        and finding.rule_id == _TARGET_RULE_ID
        and finding.file_path == seed_rel_path,
        detail=str(finding),
    )

    proposal = result.proposal
    _add(
        "D10.4_exactly_one_linked_proposal",
        proposal is not None
        and proposal.action_ids == [_EXPECTED_ACTION_ID]
        and proposal.scope_files == [seed_rel_path],
        detail=str(proposal),
    )
    _add(
        "D10.5_risk_and_approval_authority_match_governed_state",
        proposal is not None
        and proposal.overall_risk == _SAFE_RISK
        and proposal.approval_authority == _SAFE_AUTO_APPROVAL_AUTHORITY
        and proposal.approved_by == _SAFE_AUTO_APPROVAL_APPROVER,
        detail=str(proposal),
    )

    chain = result.chain
    _add(
        "D10.6_execution_reaches_completed",
        chain is not None and chain.lifecycle_status == _COMPLETED_STATUS,
        detail=str(chain.lifecycle_status if chain else None),
    )
    has_consequence = (
        chain is not None
        and chain.pre_execution_sha is not None
        and chain.post_execution_sha is not None
    )
    _add("D10.7_completed_has_durable_consequence", has_consequence)
    _add(
        "D10.8_consequence_belongs_to_exact_proposal",
        chain is not None
        and proposal is not None
        and chain.proposal.proposal_id == proposal.proposal_id,
    )
    _add(
        "D10.9_consequence_has_non_null_pre_post_sha",
        has_consequence,
        detail=f"pre={chain.pre_execution_sha if chain else None} "
        f"post={chain.post_execution_sha if chain else None}",
    )
    _add(
        "D10.10_post_sha_differs_from_pre_sha",
        has_consequence
        and chain is not None
        and chain.pre_execution_sha != chain.post_execution_sha,
    )
    _add(
        "D10.11_files_changed_is_exactly_the_seed_file",
        chain is not None and chain.files_changed == [seed_rel_path],
        detail=str(chain.files_changed if chain else None),
    )
    _add(
        "D10.12_finding_resolved_and_still_linked",
        result.finding_final_status == _RESOLVED_STATUS
        and proposal is not None
        and result.finding_final_proposal_id == proposal.proposal_id,
        detail=f"status={result.finding_final_status} "
        f"proposal_id={result.finding_final_proposal_id}",
    )
    _add(
        "D10.13_reaudit_no_longer_reports_violation",
        result.reaudit_clean and result.reaudit_matches_count == 0,
    )
    _add(
        "D10.14_clone_intent_hash_unchanged",
        intent_hash_before == intent_hash_after,
        detail=f"before={intent_hash_before} after={intent_hash_after}",
    )
    _add("D10.15_invoking_repo_fingerprint_unchanged", source_fingerprint_matches)

    return assertions


# ID: 906529d3-3398-476d-a1ac-e7ea9014bb72
async def run_consequence_chain(source: GitService, demo_state_dir: Path) -> PhaseResult:
    """Drive the full ADR-155 Phase 2 scenario: seed, chain, evidence, cleanup.

    Orchestrates Phase 1's isolation substrate and the Phase 2 chain
    scenario without implementing a demo-only substitute for either (D6).
    Always returns a ``PhaseResult`` carrying every D10 assertion — never
    raises for a scenario-level failure, only for a genuine substrate fault
    (e.g. Docker unavailable), which is itself a pre-flight condition
    distinct from the chain scenario's own pass/fail.
    """
    fingerprint_before = capture_fingerprint(source)
    head = source.get_current_commit()

    identity = generate_run_identity(demo_state_dir)
    clone = create_isolated_clone(source, head, identity)
    prove_clone_isolation(clone, head)
    clone.configure_local_identity(
        email="core-demo@localhost", name="CORE Isolated Consequence-Chain Demo"
    )
    intent_hash_before = hash_directory(clone.repo_path / ".intent")

    run_id_short = identity.run_id[:8]
    seed_rel_path = seed_relative_path(run_id_short)
    seed_existed_before = clone.is_committed(seed_rel_path)
    pre_seed_head = clone.get_current_commit()
    write_and_commit_seed(clone, run_id_short)
    post_seed_head = clone.get_current_commit()
    seed_commit_files = await clone.diff_file_names(pre_seed_head, post_seed_head)

    compose_file = clone.repo_path / "infra" / "demo" / "compose.yaml"
    compose_env = {"RUN_ID": identity.run_id}
    path = os.environ.get("PATH")
    if path:
        compose_env["PATH"] = path

    infra_healthy = False
    result: ChainScenarioResult
    try:
        up_result = await compose_up(identity.run_id, compose_file, compose_env)
        infra_healthy = up_result.returncode == 0

        if infra_healthy:
            pg_port = await _container_host_port(identity.run_id, "postgres", 5432)
            qdrant_port = await _container_host_port(identity.run_id, "qdrant", 6333)
            _write_child_env(clone.repo_path, pg_port, qdrant_port)

            child_env = {}
            if path:
                child_env["PATH"] = path
            await run_child_process(
                [
                    sys.executable,
                    "src/cli/logic/demo/scenario_runner.py",
                    str(identity.state_dir),
                    seed_rel_path,
                    identity.run_id,
                ],
                cwd=clone.repo_path,
                env=child_env,
            )
            result = ChainScenarioResult.from_dict(
                read_state_json(identity.state_dir / "scenario_result.json")
            )
        else:
            result = ChainScenarioResult(
                run_id=identity.run_id,
                seed_rel_path=seed_rel_path,
                finding=None,
                finding_matches_count=0,
                proposal=None,
                chain=None,
                reaudit_clean=False,
                reaudit_matches_count=1,
                error="disposable infrastructure failed to become healthy",
            )
    finally:
        await compose_down(identity.run_id, compose_file, compose_env)

    intent_hash_after = hash_directory(clone.repo_path / ".intent")
    fingerprint_after = capture_fingerprint(source)
    source_fingerprint_matches = fingerprint_before.matches(fingerprint_after)

    assertions = _evaluate_assertions(
        infra_healthy=infra_healthy,
        seed_commit_files=seed_commit_files,
        seed_rel_path=seed_rel_path,
        intent_hash_before=intent_hash_before,
        intent_hash_after=intent_hash_after,
        result=result,
        source_fingerprint_matches=source_fingerprint_matches,
    )
    assertions.insert(
        0,
        AssertionResult(
            name="D7.seed_path_absent_at_cloned_baseline",
            passed=not seed_existed_before,
        ),
    )

    ok = all(a.passed for a in assertions)

    if ok:
        cleanup_run(identity, demo_state_dir)
    else:
        # D11: on failure, the workspace is retained for diagnosis rather
        # than cleaned up — infra is already down (the `finally` above),
        # only the filesystem state remains. Phase 3's CLI surface is what
        # prints this path to an operator and offers
        # `core-admin demo cleanup <run_id>`; this orchestration layer only
        # guarantees the state survives to be inspected.
        logger.warning(
            "Consequence-chain scenario run %s failed: %s — workspace retained at %s",
            identity.run_id,
            [a.name for a in assertions if not a.passed],
            identity.state_dir,
        )

    return PhaseResult(run_id=identity.run_id, ok=ok, assertions=assertions)
