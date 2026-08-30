# tests/will/autonomy/test_build_test_for_symbol_e2e_acceptance.py
"""flow.build_test_for_symbol end-to-end integration proof (#843 / URS §G8).

G8's gap text (production-readiness manifest): "No end-to-end integration
test of the governed mutation chain (cognitive delegate -> write -> sandbox
-> evidence). Integration INFRASTRUCTURE exists — the specific chain test
does not." The #843 recon confirmed real integration coverage exists for the
`fix.ids`/RemediationCeremony flow (ADR-154, test_adr154_e2e_acceptance.py)
but nothing crosses real component boundaries for flow.build_test_for_symbol
specifically — every existing test of build.test_for_symbol/TestGenCognitive-
Delegate mocks the cognitive service, the sandbox, or both.

Three tests here, following the ADR-154 test's own template (real DB against
core_test, one stubbed nondeterministic-external boundary, everything else
real):

  1. happy path: generate.test_snippet (real TestGenCognitiveDelegate + real
     PromptModelIterativeAgent generate/accept loop, including a real
     test.candidate_validate pytest run during generation) -> build.test_for_
     symbol (real write) -> test.sandbox_validate (real pytest run inside the
     real hermetic git worktree ADR-106 sandboxes the flow into) -> real git
     commit -> real core.proposal_consequences row. Only PromptModel.invoke
     is stubbed — the one genuinely external, nondeterministic LLM call.

  2. no-output fails closed: the stubbed LLM never returns a ```python fence,
     so generation exhausts its budget, the cognitive step raises
     CognitiveStepError, and FlowExecutor's required-step-halt semantics
     stop the flow before build.test_for_symbol ever runs — no file written,
     HEAD unmoved, proposal FAILED.

  3. sandbox-validation failure produces no commit: the accepted candidate
     passes generation-time acceptance for real, but the flow's final
     required step (test.sandbox_validate) is forced to fail via a narrow
     patch of test_actions.run_tests keyed on action_id — proving that a
     downstream sandbox-validation failure means the flow-sandboxed write
     never propagates out of its hermetic worktree (ADR-106/107: propagate_
     changes only runs when the flow succeeds) and no commit lands.

IntentGuard's tier-1 path guard (FileHandler._guard_paths) is neutralized at
the class level, not just on one instance, because ADR-106 sandboxing builds
a brand-new FileHandler for the scoped worktree context
(SandboxLifecycle._make_scoped_context) rather than copying the caller's —
the same reason test_flow_sandbox_lifecycle.py's _make_sandbox neutralizes
it, generalized to cover both the main and scoped contexts a flow proposal
touches.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from body.atomic import test_actions as test_actions_module
from body.infrastructure.storage.file_handler import FileHandler
from body.services.service_registry import service_registry
from shared.action_types import ActionResult
from shared.ai.prompt_model import PromptModel
from shared.context import CoreContext
from shared.infrastructure.database.session_manager import get_session
from shared.infrastructure.git_service import GitService
from will.autonomy.proposal import (
    Proposal,
    ProposalAction,
    ProposalScope,
    ProposalStatus,
    RiskAssessment,
)
from will.autonomy.proposal_executor import ProposalExecutor
from will.autonomy.proposal_repository import ProposalRepository
from will.workers.violation_executor import ViolationExecutorWorker


pytestmark = [pytest.mark.integration]

_SOURCE_FILE = "src/mymod/example.py"
_TEST_FILE = "tests/mymod/example/test_generated.py"
"""source_to_test_path's fallback mapping (no real test_coverage.yaml in this
bare repo): src/{p}.py -> tests/{p}/test_generated.py — not tests/{p}/test_{name}.py."""
_SOURCE_BODY = "def add(a: int, b: int) -> int:\n    return a + b\n"

_ACCEPTED_FENCE = (
    "```python\n"
    "from __future__ import annotations\n\n\n"
    "from mymod.example import add\n\n\n"
    "def test_add() -> None:\n"
    "    assert add(1, 2) == 3\n"
    "```"
)

_NO_FENCE_RESPONSE = "Sorry, I can't help with that request."


class _StubCognitiveService:
    """Minimal stand-in for CognitiveService — only client acquisition is
    exercised; the LLM call itself is stubbed at PromptModel.invoke, so what
    this returns is never actually invoked."""

    async def aget_client_for_role(self, role: str) -> MagicMock:
        return MagicMock(name=f"stub_client_for_{role}")


def _run(args: list[str], cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture(autouse=True)
def _prime_service_registry() -> None:
    """Mirror production bootstrap so service_registry.session() acquires a
    live session against core_test everywhere it is used inside the chain."""
    service_registry.prime(get_session)


@pytest.fixture(autouse=True)
def _no_subprocess_coverage_crosstalk(monkeypatch: pytest.MonkeyPatch) -> None:
    """These tests spawn real pytest subprocesses (test.candidate_validate /
    test.sandbox_validate against the sandboxed worktree). Identical to
    test_adr154_e2e_acceptance.py's own documented workaround: pytest-cov's
    subprocess-coverage auto-recording (gated on COV_CORE_DATAFILE) captures
    statement-only data (no COV_CORE_BRANCH, since that's only set by
    --cov-branch) that then can't merge with this repo's branch-mode main
    data at teardown. Test-only env stripping; no production code touched,
    no coverage of src/ lost — the subprocess only runs formatting/pytest
    tooling, not src/ itself."""
    for _var in (
        "COV_CORE_SOURCE",
        "COV_CORE_CONFIG",
        "COV_CORE_DATAFILE",
        "COV_CORE_BRANCH",
        "COV_CORE_CONTEXT",
    ):
        monkeypatch.delenv(_var, raising=False)


@pytest.fixture(autouse=True)
def _neutralize_intent_guard_path_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """This bare temp repo carries no real .intent/ vocabulary projection —
    IntentGuard's tier-1 path invariant loads that from each FileHandler's
    own repo_path and would block every write, including inside the scoped
    worktree FileHandler ADR-106 sandboxing builds fresh. Class-level, not
    instance-level (test_flow_sandbox_lifecycle.py's per-instance approach
    doesn't reach the scoped copy)."""

    def _no_guard(self: FileHandler, *args: object, **kwargs: object) -> None:
        return None

    monkeypatch.setattr(FileHandler, "_guard_paths", _no_guard)


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Real, standalone git repository with one committed source module and
    a pyproject.toml mirroring this repo's own pythonpath=["src"] pytest
    config, so a generated test's `from mymod.example import add` resolves
    exactly as it would in the real repo.

    code.imports.generated_must_resolve (the in-process IntentGuard check
    the cognitive step's acceptance loop runs) uses real
    importlib.util.find_spec against the CURRENT process's sys.path — it
    has no notion of a repo_root parameter, unlike the subprocess pytest
    runs (test.candidate_validate / test.sandbox_validate), which get
    module resolution for free from this repo's own pythonpath=["src"]
    ini option applied to the *worktree's* pyproject.toml. syspath_prepend
    is this test's equivalent for the in-process check, self-cleaning at
    teardown."""
    monkeypatch.syspath_prepend(str(tmp_path / "src"))
    _run(["git", "init"], tmp_path)
    _run(["git", "config", "user.email", "e2e@test.local"], tmp_path)
    _run(["git", "config", "user.name", "E2E Test"], tmp_path)
    _run(["git", "config", "commit.gpgsign", "false"], tmp_path)

    (tmp_path / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\npythonpath = ["src"]\n', encoding="utf-8"
    )
    source_path = tmp_path / _SOURCE_FILE
    source_path.parent.mkdir(parents=True, exist_ok=True)
    (source_path.parent / "__init__.py").write_text("", encoding="utf-8")
    source_path.write_text(_SOURCE_BODY, encoding="utf-8")

    _run(["git", "add", "-A"], tmp_path)
    _run(["git", "commit", "-m", "initial"], tmp_path)
    return tmp_path


def _make_context(repo: Path) -> CoreContext:
    from body.atomic.executor import ActionExecutor

    file_handler = FileHandler(str(repo))
    ctx = CoreContext(
        registry=service_registry,
        git_service=GitService(repo),
        knowledge_service=MagicMock(),
        file_handler=file_handler,
        file_service=MagicMock(),
        cognitive_service=_StubCognitiveService(),
    )
    ctx.action_executor = ActionExecutor(ctx)
    return ctx


def _build_test_gen_proposal(goal: str) -> Proposal:
    return Proposal(
        goal=goal,
        actions=[
            ProposalAction(
                flow_id="flow.build_test_for_symbol",
                parameters={
                    "source_file": _SOURCE_FILE,
                    "symbol_name": "add",
                    "symbol_kind": "function",
                    "signature": "def add(a: int, b: int) -> int",
                },
                order=0,
            )
        ],
        scope=ProposalScope(files=[_TEST_FILE]),
        risk=RiskAssessment(overall_risk="moderate"),
        status=ProposalStatus.APPROVED,
        approval_required=True,
        approved_by="e2e-governor",
        approval_authority="principal.governor",
    )


async def _fetch_proposal_row(proposal_id: str) -> dict:
    async with service_registry.session() as session:
        result = await session.execute(
            text(
                "SELECT status, consequence_recorded_at "
                "FROM core.autonomous_proposals WHERE proposal_id = :pid"
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
                "files_changed FROM core.proposal_consequences "
                "WHERE proposal_id = :pid"
            ),
            {"pid": proposal_id},
        )
        row = result.mappings().first()
        return dict(row) if row is not None else {}


async def test_build_test_for_symbol_happy_path_reaches_completed_with_durable_consequence(
    repo: Path,
    db_session: AsyncSession,
) -> None:
    core_context = _make_context(repo)
    baseline_sha = core_context.git_service.get_current_commit()

    worker = ViolationExecutorWorker(core_context=core_context)
    await worker._register()

    proposal = _build_test_gen_proposal("Generate a test for mymod.example.add")
    async with service_registry.session() as session:
        proposal_id = await ProposalRepository(session).create(proposal)
        await session.commit()

    with patch.object(PromptModel, "invoke", new=AsyncMock(return_value=_ACCEPTED_FENCE)):
        executor = ProposalExecutor(core_context)
        result = await executor.execute(
            proposal_id, claimed_by=worker._worker_uuid, write=True
        )

    assert result["ok"] is True, result
    assert result["lifecycle_status"] == "completed", result

    written = (repo / _TEST_FILE).read_text(encoding="utf-8")
    assert "def test_add" in written
    assert "from mymod.example import add" in written

    post_sha = core_context.git_service.get_current_commit()
    assert post_sha != baseline_sha, "a real commit must have advanced HEAD"

    final_row = await _fetch_proposal_row(proposal_id)
    assert final_row["status"] == "completed"
    assert final_row["consequence_recorded_at"] is not None

    consequence = await _fetch_consequence_row(proposal_id)
    assert consequence, "a durable core.proposal_consequences row must exist"
    assert consequence["pre_execution_sha"] == baseline_sha
    assert consequence["post_execution_sha"] == post_sha
    assert _TEST_FILE in {f["path"] for f in consequence["files_changed"]}


async def test_build_test_for_symbol_no_output_fails_closed_with_no_write(
    repo: Path,
    db_session: AsyncSession,
) -> None:
    core_context = _make_context(repo)
    baseline_sha = core_context.git_service.get_current_commit()

    worker = ViolationExecutorWorker(core_context=core_context)
    await worker._register()

    proposal = _build_test_gen_proposal("Generate a test — forced no-fence response")
    async with service_registry.session() as session:
        proposal_id = await ProposalRepository(session).create(proposal)
        await session.commit()

    with patch.object(PromptModel, "invoke", new=AsyncMock(return_value=_NO_FENCE_RESPONSE)):
        executor = ProposalExecutor(core_context)
        result = await executor.execute(
            proposal_id, claimed_by=worker._worker_uuid, write=True
        )

    assert result["ok"] is False, result
    assert result["lifecycle_status"] == "failed", result
    assert not (repo / _TEST_FILE).exists(), (
        "no-output must fail closed — no test file may be written"
    )
    assert core_context.git_service.get_current_commit() == baseline_sha, (
        "no-output must fail closed — HEAD must not move"
    )

    final_row = await _fetch_proposal_row(proposal_id)
    assert final_row["status"] == "failed"
    assert final_row["consequence_recorded_at"] is None


async def test_build_test_for_symbol_sandbox_validate_failure_produces_no_commit(
    repo: Path,
    db_session: AsyncSession,
) -> None:
    core_context = _make_context(repo)
    baseline_sha = core_context.git_service.get_current_commit()

    worker = ViolationExecutorWorker(core_context=core_context)
    await worker._register()

    proposal = _build_test_gen_proposal(
        "Generate a test for mymod.example.add — forced sandbox-validate failure"
    )
    async with service_registry.session() as session:
        proposal_id = await ProposalRepository(session).create(proposal)
        await session.commit()

    real_run_tests = test_actions_module.run_tests

    async def _forced_sandbox_validate_failure(*args: object, **kwargs: object):
        if kwargs.get("action_id") == "test.sandbox_validate":
            return ActionResult(
                action_id="test.sandbox_validate",
                ok=False,
                data={
                    "error": (
                        "forced failure — proves the sandbox-validate-fails "
                        "-> no-commit path"
                    )
                },
                duration_sec=0.0,
            )
        return await real_run_tests(*args, **kwargs)

    with (
        patch.object(PromptModel, "invoke", new=AsyncMock(return_value=_ACCEPTED_FENCE)),
        patch.object(
            test_actions_module, "run_tests", new=_forced_sandbox_validate_failure
        ),
    ):
        executor = ProposalExecutor(core_context)
        result = await executor.execute(
            proposal_id, claimed_by=worker._worker_uuid, write=True
        )

    assert result["ok"] is False, result
    assert result["lifecycle_status"] == "failed", result
    # ADR-106/107: a flow's sandbox writes land in a throwaway worktree and
    # are propagated to the main tree only on flow success — a failure at
    # the final required step means the write never leaves the worktree at
    # all, not merely that it gets rolled back after landing.
    assert not (repo / _TEST_FILE).exists(), (
        "sandbox-validation failure must mean the write never propagates "
        "out of the hermetic worktree"
    )
    assert core_context.git_service.get_current_commit() == baseline_sha, (
        "sandbox-validation failure must not advance HEAD — no commit"
    )

    final_row = await _fetch_proposal_row(proposal_id)
    assert final_row["status"] == "failed"
    assert final_row["consequence_recorded_at"] is None
