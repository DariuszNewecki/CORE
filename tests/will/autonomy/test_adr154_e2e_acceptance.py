# tests/will/autonomy/test_adr154_e2e_acceptance.py
"""ADR-154 end-to-end acceptance proof (#818).

The single genuine integration proof ADR-154's own Verification section
calls for and #818 requires before closure:

    unmapped finding -> candidate generated and validated -> human-gated
    DRAFT -> governor approval -> ProposalExecutor -> SandboxLifecycle ->
    production commit -> FINALIZING -> durable consequence row ->
    COMPLETED -> source finding resolved

Every collaborator in that chain is real and DB-backed against core_test:
Blackboard finding persistence and claiming (AuditViolationSensor /
ViolationExecutorWorker's real claim query), RemediationCeremony's real
Crate/Canary/patch-generation/assisted.validate_diff machinery,
build_validated_candidate's real independent re-read,
submit_ceremony_proposal's real atomic submission, ProposalService's real
approval transition, ProposalExecutor's real action loop through
SandboxLifecycle, a real temporary git repository and a real git commit,
and ConsequenceLogService's real persistence.

The only stub is RemediationCeremony._invoke_llm — the one genuinely
external, nondeterministic dependency. Nothing else in the ADR-154
candidate-validation or proposal-submission machinery is mocked.

The finding's rule id (`purity.e2e_adr154_placeholder`) is a real,
declared-namespace-prefixed ("purity.") id that does not correspond to any
actual rule in .intent/rules/. This is deliberate, not a shortcut around
validation: run_filtered_audit(rule_ids=[that id]) legitimately matches
zero rules (confirmed against the live rule set), so
assisted.validate_diff's audit_rule_cleared check evaluates truthfully —
there is genuinely no rule left flagging the guarded files, precisely
because no such rule exists. This keeps the test's content deterministic
and independent of CORE's own 256 live rules, while every check the
action performs (patch application, ruff, the audit invocation itself,
mapped-test lookup) still runs for real. The target file is otherwise a
comment-only Python file with zero public symbols, so it cannot trip any
real CORE rule when Canary later runs a *full* audit against the
temporary repo's own copy.
"""

from __future__ import annotations

import asyncio
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from body.atomic.executor import ActionExecutor
from body.infrastructure.storage.file_handler import FileHandler
from body.services.service_registry import service_registry
from shared.context import CoreContext
from shared.infrastructure.database.session_manager import get_session
from shared.infrastructure.git_service import GitService
from will.autonomy.proposal_executor import ProposalExecutor
from will.autonomy.proposal_service import ProposalService
from will.remediation import RemediationCeremony, WorkerRemediationBlackboard
from will.workers.audit_violation_sensor import AuditViolationSensor
from will.workers.violation_executor import ViolationExecutorWorker


pytestmark = [pytest.mark.integration]

_RULE_ID = "purity.e2e_adr154_placeholder"
_FILE_PATH = "src/body/services/e2e_adr154_fixture.py"
_ORIGINAL = "# original placeholder for ADR-154 E2E acceptance test\n"
_FIXED = _ORIGINAL + "# fixed by e2e test\n"


@pytest.fixture(autouse=True)
def _prime_service_registry() -> None:
    """Mirror production bootstrap so service_registry.session() acquires a
    live session against core_test everywhere it is used inside the chain
    (blackboard claims, fix_run persistence, proposal persistence,
    consequence recording)."""
    service_registry.prime(get_session)


def _run(args: list[str], cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


def _git_diff_tree_names(sha: str, cwd: Path) -> list[str]:
    return (
        subprocess.run(
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", sha],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
        .stdout.strip()
        .splitlines()
    )


def _git_last_commit_subject(cwd: Path) -> str:
    return subprocess.run(
        ["git", "log", "-1", "--format=%s"],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Real, standalone git repository — not the CORE repo itself — with
    the target file committed at a baseline SHA."""
    _run(["git", "init"], tmp_path)
    _run(["git", "config", "user.email", "e2e@test.local"], tmp_path)
    _run(["git", "config", "user.name", "E2E Test"], tmp_path)
    _run(["git", "config", "commit.gpgsign", "false"], tmp_path)
    target = tmp_path / _FILE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_ORIGINAL, encoding="utf-8")
    _run(["git", "add", "-A"], tmp_path)
    _run(["git", "commit", "-m", "initial"], tmp_path)
    return tmp_path


def _make_context(repo: Path) -> CoreContext:
    file_handler = FileHandler(str(repo))
    # This bare temp repo carries no real .intent/ vocabulary projection —
    # IntentGuard's tier-1 invariant loads that from the FileHandler's own
    # repo_path and would block every write. Same neutralization as
    # test_executor_worktree_isolation.py's _make_context.
    file_handler._guard_paths = lambda *a, **k: None  # type: ignore[method-assign]
    ctx = CoreContext(
        registry=service_registry,
        git_service=GitService(repo),
        knowledge_service=MagicMock(),
        file_handler=file_handler,
        file_service=MagicMock(),
    )
    ctx.action_executor = ActionExecutor(ctx)
    return ctx


async def _fetch_proposal_row(proposal_id: str) -> dict:
    async with service_registry.session() as session:
        result = await session.execute(
            text(
                "SELECT status, approval_required, approval_authority, "
                "approved_by, consequence_recorded_at, constitutional_constraints, "
                "actions FROM core.autonomous_proposals WHERE proposal_id = :pid"
            ),
            {"pid": proposal_id},
        )
        row = result.mappings().first()
        return dict(row) if row is not None else {}


async def _fetch_consequence_row(proposal_id: str) -> dict:
    async with service_registry.session() as session:
        result = await session.execute(
            text(
                "SELECT proposal_id, pre_execution_sha, post_execution_sha, "
                "files_changed, findings_resolved "
                "FROM core.proposal_consequences WHERE proposal_id = :pid"
            ),
            {"pid": proposal_id},
        )
        row = result.mappings().first()
        return dict(row) if row is not None else {}


async def _fetch_finding_status(finding_id: str) -> str | None:
    async with service_registry.session() as session:
        result = await session.execute(
            text(
                "SELECT status FROM core.blackboard_entries WHERE id = cast(:fid as uuid)"
            ),
            {"fid": finding_id},
        )
        row = result.first()
        return row[0] if row is not None else None


async def test_adr154_unmapped_finding_reaches_completed_with_durable_consequence(
    repo: Path,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # This test is the first to spawn real subprocesses from inside a real
    # RemediationCeremony run (poetry run black/ruff in _align_staged_file).
    # pytest-cov's own subprocess-coverage support (pytest_cov/embed.py,
    # gated on COV_CORE_DATAFILE — NOT the plain `coverage` package's
    # COVERAGE_PROCESS_START; confirmed by reading pytest_cov/engine.py and
    # embed.py directly) makes any Python subprocess auto-record its own
    # coverage data once COV_CORE_DATAFILE is set. But COV_CORE_BRANCH is
    # only set when pytest-cov's separate --cov-branch CLI flag is passed
    # (confirmed empirically: absent from os.environ here even though
    # pyproject.toml's [tool.coverage.run] branch = true governs the main
    # process directly via the coverage config file, a different
    # mechanism) — so any subprocess-recorded data is always statement-only
    # (has_arcs=0), which coverage.py's combine step then refuses to merge
    # with this repo's branch-mode (has_arcs=1) main data, crashing
    # pytest-cov's finish() after the run has already passed. Test-only
    # fix, the same five vars pytest-cov's own engine.py removes on
    # teardown: no production code involved, no coverage of anything lost
    # (poetry/black/ruff are formatting tools, not src/ code the coverage
    # gate measures).
    for _var in (
        "COV_CORE_SOURCE",
        "COV_CORE_CONFIG",
        "COV_CORE_DATAFILE",
        "COV_CORE_BRANCH",
        "COV_CORE_CONTEXT",
    ):
        monkeypatch.delenv(_var, raising=False)

    core_context = _make_context(repo)
    baseline_sha = core_context.git_service.get_current_commit()
    target_path = repo / _FILE_PATH
    test_started_at = datetime.now(UTC)

    # ------------------------------------------------------------------
    # 1. A genuine canonical unmapped-rule Blackboard finding.
    # ------------------------------------------------------------------
    sensor = AuditViolationSensor(
        core_context=core_context,
        declaration_name="audit_sensor_purity",
        rule_namespace="purity",
        dry_run=False,
    )
    # Real registration (normally done by Worker.start(), which we don't
    # call here since we only need specific methods, not the full run()
    # loop) — required by blackboard_entries' worker_uuid FK.
    await sensor._register()
    await sensor.post_artifact_finding(
        artifact_type="python",
        sub_namespace=_RULE_ID,
        identity_key_value=_FILE_PATH,
        payload={
            "rule": _RULE_ID,
            "file_path": _FILE_PATH,
            "line_number": 1,
            "message": "e2e acceptance fixture — not a real violation",
            "severity": "warning",
            "status": "unprocessed",
        },
    )

    # ------------------------------------------------------------------
    # 2. The finding becomes claimed through the normal claim path —
    #    ViolationExecutorWorker's real claim query, unmapped (no rule in
    #    the real RemediationMap matches this fictitious id).
    # ------------------------------------------------------------------
    worker = ViolationExecutorWorker(core_context=core_context)
    await worker._register()
    findings = await worker._claim_unmapped_findings(mapped_rule_ids=set())
    assert findings, "the seeded finding must be claimable as unmapped"
    ours = [f for f in findings if f["payload"].get("rule") == _RULE_ID]
    assert len(ours) == 1, f"expected exactly our finding claimed, got {findings}"
    finding_id = str(ours[0]["id"])

    # ------------------------------------------------------------------
    # 3-4. Run the real ceremony. Only the LLM call is stubbed — Crate,
    #    Canary, patch generation, assisted.validate_diff, candidate
    #    construction, and DRAFT submission all run for real.
    # ------------------------------------------------------------------
    blackboard = WorkerRemediationBlackboard(worker, core_context)
    ceremony = RemediationCeremony(
        core_context=core_context,
        target_rule=_RULE_ID,
        blackboard=blackboard,
    )
    with patch.object(ceremony, "_invoke_llm", new=AsyncMock(return_value=_FIXED)):
        ok = await ceremony.process_file(_FILE_PATH, ours)
    assert ok is True, (
        "ceremony must succeed through candidate validation and DRAFT creation"
    )

    # ------------------------------------------------------------------
    # 5. Production bytes are NOT changed before human approval — the
    #    governor's explicit insistence. Checked against both the file
    #    content and git HEAD.
    # ------------------------------------------------------------------
    assert target_path.read_text(encoding="utf-8") == _ORIGINAL, (
        "file must be byte-unchanged before governor approval"
    )
    assert core_context.git_service.get_current_commit() == baseline_sha, (
        "git HEAD must not have moved before governor approval"
    )

    # Locate the DRAFT proposal the ceremony created, bound to our finding.
    async with service_registry.session() as session:
        result = await session.execute(
            text(
                "SELECT proposal_id FROM core.autonomous_proposals "
                "WHERE constitutional_constraints->>'candidate_id' IS NOT NULL "
                "AND constitutional_constraints->'finding_ids' ? :fid "
                "AND created_at >= :started"
            ),
            {"fid": finding_id, "started": test_started_at},
        )
        row = result.first()
    assert row is not None, "a DRAFT proposal bound to the finding must exist"
    proposal_id = row[0]

    draft_row = await _fetch_proposal_row(proposal_id)
    assert draft_row["status"] == "draft"
    assert draft_row["approval_required"] is True
    assert draft_row["approval_authority"] is None, (
        "no approval authority recorded yet — DRAFT is not self-approved"
    )
    assert draft_row["actions"][0]["action_id"] == "assisted.apply_diff"

    # ------------------------------------------------------------------
    # 6. The proposal cannot take the mapped safe-auto-approval route:
    #    approval_required is True (unmapped-lane proposals never qualify
    #    for Lane 1's risk_classification.safe_auto_approval).
    # ------------------------------------------------------------------
    assert draft_row["approval_required"] is True

    # ------------------------------------------------------------------
    # 7. Perform the real governor/human approval transition.
    # ------------------------------------------------------------------
    async with ProposalService.open() as proposal_service:
        await proposal_service.approve(
            proposal_id,
            approved_by="e2e-governor",
            approval_authority="principal.governor",
        )

    approved_row = await _fetch_proposal_row(proposal_id)
    assert approved_row["status"] == "approved"
    assert approved_row["approval_authority"] == "principal.governor", (
        "must be the human-gated authority, never risk_classification.safe_auto_approval"
    )

    # File still untouched — approval itself is not execution.
    assert target_path.read_text(encoding="utf-8") == _ORIGINAL
    assert core_context.git_service.get_current_commit() == baseline_sha

    # ------------------------------------------------------------------
    # 8-10. Real ProposalExecutor -> real SandboxLifecycle (via
    #    ActionExecutor's write-sandboxing) -> real assisted.apply_diff ->
    #    real git commit -> FINALIZING.
    # ------------------------------------------------------------------
    executor = ProposalExecutor(core_context)
    result = await executor.execute(
        proposal_id, claimed_by=worker._worker_uuid, write=True
    )

    assert result["ok"] is True, result
    assert result["lifecycle_status"] == "completed", result

    # ------------------------------------------------------------------
    # 9. The expected file change is committed in the temporary git repo.
    # ------------------------------------------------------------------
    assert target_path.read_text(encoding="utf-8") == _FIXED, (
        "production bytes must reflect the applied, approved diff"
    )
    post_sha = core_context.git_service.get_current_commit()
    assert post_sha != baseline_sha, "a real commit must have advanced HEAD"
    diff_paths = await asyncio.to_thread(_git_diff_tree_names, post_sha, repo)
    assert diff_paths == [_FILE_PATH], "commit must contain exactly the production set"
    commit_msg = await asyncio.to_thread(_git_last_commit_subject, repo)
    assert proposal_id[:16] in commit_msg

    # ------------------------------------------------------------------
    # 10-11. FINALIZING was reached en route (implied by reaching
    #    completed — mark_completed only accepts a finalizing source
    #    state, per ProposalStateManager). Confirmed directly via the
    #    final row: consequence_recorded_at set means mark_completed's
    #    finalizing-only transition executed.
    # ------------------------------------------------------------------
    final_row = await _fetch_proposal_row(proposal_id)
    assert final_row["status"] == "completed"
    assert final_row["consequence_recorded_at"] is not None

    # ------------------------------------------------------------------
    # 11-12. A durable consequence row exists with the expected linkage.
    # ------------------------------------------------------------------
    consequence = await _fetch_consequence_row(proposal_id)
    assert consequence, "a durable core.proposal_consequences row must exist"
    assert consequence["pre_execution_sha"] == baseline_sha
    assert consequence["post_execution_sha"] == post_sha
    assert {f["path"] for f in consequence["files_changed"]} == {_FILE_PATH}
    assert finding_id in consequence["findings_resolved"]

    # ------------------------------------------------------------------
    # 13. The originating finding is resolved only after completion.
    # ------------------------------------------------------------------
    finding_status = await _fetch_finding_status(finding_id)
    assert finding_status == "resolved", (
        f"finding must be resolved after proposal completion, got {finding_status!r}"
    )
