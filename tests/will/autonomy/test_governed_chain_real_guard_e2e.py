"""The governed mutation chain with the REAL write guard in place (#950 / G8).

test_build_test_for_symbol_e2e_acceptance.py proves the chain (real Worker,
DB, sandbox, commit, consequence, blackboard) but neutralises
FileHandler._guard_paths at class level, because its bare temp repo has no
.intent/ vocabulary projection and the guard would block every write. So it
cannot show that the guard participates in the integrated chain -- and the
#949 traversal defect survived that suite.

Here the guard stays real. Only the vocabulary projection is short-circuited
to a healthy empty placeholder (the same seam the IntentGuard unit tests
use); IntentGuard itself, its .intent/ hard invariant, target-class dispatch
and FileHandler canonicalisation all run, in both the main-tree FileHandler
and the fresh one ADR-106 sandboxing builds for the scoped worktree.
PromptModel.invoke stays the only stubbed nondeterministic boundary.

  1. An authorized mutation (flow.build_test_for_symbol) reaches COMPLETED
     through ProposalConsumerWorker with the real guard: file written,
     commit landed, durable consequence, blackboard evidence.
  2. A protected-path mutation through the SAME orchestration path
     (file.create into .intent/, spelled directly and via a scratch
     traversal) is refused by the guard's .intent/ hard invariant: proposal
     FAILED, nothing under .intent/ written, HEAD unmoved, blackboard
     records the failure. Verified to fail when the guard is neutralised.

     Scope note: file.create consults IntentGuard on the raw path before
     FileHandler, so this route refused the traversal spelling even before
     the #949 fix; #949's FileHandler/IntentGuard ordering defect is pinned
     by tests/body/infrastructure/storage/test_file_handler__intent_traversal.py.

Integration: real core_test DB (pytestmark below).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from body.infrastructure.storage.file_handler import FileHandler
from body.services.service_registry import service_registry
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
from will.autonomy.proposal_repository import ProposalRepository
from will.workers.proposal_consumer_worker import ProposalConsumerWorker


pytestmark = [pytest.mark.integration]

_SOURCE_FILE = "src/mymod/example.py"
_TEST_FILE = "tests/mymod/example/test_generated.py"
_SOURCE_BODY = "def add(a: int, b: int) -> int:\n    return a + b\n"
_LAW_FILE = ".intent/rules/law.json"
_ACCEPTED_FENCE = (
    "```python\n"
    "from __future__ import annotations\n\n\n"
    "from mymod.example import add\n\n\n"
    "def test_add() -> None:\n"
    "    assert add(1, 2) == 3\n"
    "```"
)


class _StubCognitiveService:
    async def aget_client_for_role(self, role: str) -> MagicMock:
        return MagicMock(name=f"stub_client_for_{role}")


def _run(args: list[str], cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture(autouse=True)
def _prime_service_registry() -> None:
    service_registry.prime(get_session)


@pytest.fixture(autouse=True)
def _no_subprocess_coverage_crosstalk(monkeypatch: pytest.MonkeyPatch) -> None:
    """Same workaround as the sibling e2e tests: real pytest subprocesses
    must not inherit pytest-cov's subprocess recording."""
    for var in (
        "COV_CORE_SOURCE",
        "COV_CORE_CONFIG",
        "COV_CORE_DATAFILE",
        "COV_CORE_BRANCH",
        "COV_CORE_CONTEXT",
    ):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture(autouse=True)
def _healthy_vocabulary_projection(monkeypatch: pytest.MonkeyPatch) -> None:
    """The ONLY guard seam touched: an empty-but-healthy vocabulary
    projection for the bare temp repo. FileHandler._guard_paths and
    IntentGuard.check_transaction run for real."""
    monkeypatch.setattr(
        "body.governance.intent_guard.load_vocabulary_projection",
        lambda _repo_path: {},
    )


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.syspath_prepend(str(tmp_path / "src"))
    _run(["git", "init"], tmp_path)
    _run(["git", "config", "user.email", "e2e@test.local"], tmp_path)
    _run(["git", "config", "user.name", "E2E Test"], tmp_path)
    _run(["git", "config", "commit.gpgsign", "false"], tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\npythonpath = ["src"]\n', encoding="utf-8"
    )
    source = tmp_path / _SOURCE_FILE
    source.parent.mkdir(parents=True, exist_ok=True)
    (source.parent / "__init__.py").write_text("", encoding="utf-8")
    source.write_text(_SOURCE_BODY, encoding="utf-8")
    law = tmp_path / _LAW_FILE
    law.parent.mkdir(parents=True, exist_ok=True)
    law.write_text("{}\n", encoding="utf-8")
    _run(["git", "add", "-A"], tmp_path)
    _run(["git", "commit", "-m", "initial"], tmp_path)
    return tmp_path


def _make_context(repo: Path) -> CoreContext:
    from body.atomic.executor import ActionExecutor

    ctx = CoreContext(
        registry=service_registry,
        git_service=GitService(repo),
        knowledge_service=MagicMock(),
        file_handler=FileHandler(str(repo)),
        file_service=MagicMock(),
        cognitive_service=_StubCognitiveService(),
    )
    ctx.action_executor = ActionExecutor(ctx)
    return ctx


def _approved(goal: str, action: ProposalAction, scope: list[str]) -> Proposal:
    return Proposal(
        goal=goal,
        actions=[action],
        scope=ProposalScope(files=scope),
        risk=RiskAssessment(overall_risk="moderate"),
        status=ProposalStatus.APPROVED,
        approval_required=True,
        approved_by="e2e-governor",
        approval_authority="principal.governor",
    )


async def _submit_and_run(core_context: CoreContext, proposal: Proposal) -> str:
    worker = ProposalConsumerWorker(core_context)
    await worker._register()
    async with service_registry.session() as session:
        proposal_id = await ProposalRepository(session).create(proposal)
        await session.commit()
    with patch.object(
        PromptModel, "invoke", new=AsyncMock(return_value=_ACCEPTED_FENCE)
    ):
        await worker.run()
    return proposal_id


async def _proposal_row(proposal_id: str) -> dict:
    async with service_registry.session() as session:
        result = await session.execute(
            text(
                "SELECT status, consequence_recorded_at, failure_reason, "
                "execution_results FROM core.autonomous_proposals "
                "WHERE proposal_id = :pid"
            ),
            {"pid": proposal_id},
        )
        row = result.mappings().first()
        return dict(row) if row is not None else {}


async def _run_complete_entry(proposal_id: str) -> dict | None:
    async with service_registry.session() as session:
        result = await session.execute(
            text(
                "SELECT payload FROM core.blackboard_entries "
                "WHERE subject = 'proposal_consumer_worker.run.complete' "
                "AND entry_type = 'report' ORDER BY created_at DESC LIMIT 50"
            )
        )
        for row in result.mappings().all():
            for entry in (row["payload"] or {}).get("results", []):
                if entry.get("proposal_id") == proposal_id:
                    return entry
    return None


def _intent_snapshot(repo: Path) -> dict[str, str]:
    return {
        p.relative_to(repo).as_posix(): p.read_text(encoding="utf-8")
        for p in sorted((repo / ".intent").rglob("*"))
        if p.is_file()
    }


async def test_authorized_mutation_completes_with_the_real_guard(
    repo: Path, db_session: AsyncSession
) -> None:
    core_context = _make_context(repo)
    baseline = core_context.git_service.get_current_commit()

    proposal_id = await _submit_and_run(
        core_context,
        _approved(
            "Generate a test for mymod.example.add (real guard)",
            ProposalAction(
                flow_id="flow.build_test_for_symbol",
                parameters={
                    "source_file": _SOURCE_FILE,
                    "symbol_name": "add",
                    "symbol_kind": "function",
                    "signature": "def add(a: int, b: int) -> int",
                },
                order=0,
            ),
            [_TEST_FILE],
        ),
    )

    assert "def test_add" in (repo / _TEST_FILE).read_text(encoding="utf-8")
    assert core_context.git_service.get_current_commit() != baseline
    row = await _proposal_row(proposal_id)
    assert row["status"] == "completed", row.get("failure_reason")
    assert row["consequence_recorded_at"] is not None
    reported = await _run_complete_entry(proposal_id)
    assert reported is not None and reported["lifecycle_status"] == "completed"


@pytest.mark.parametrize(
    "target", [".intent/rules/injected.json", "var/tmp/../../.intent/injected.json"]
)
async def test_protected_path_mutation_is_refused_by_the_real_guard(
    repo: Path, db_session: AsyncSession, target: str
) -> None:
    core_context = _make_context(repo)
    baseline = core_context.git_service.get_current_commit()
    before = _intent_snapshot(repo)

    proposal_id = await _submit_and_run(
        core_context,
        _approved(
            f"Attempt a write into .intent/ via {target}",
            ProposalAction(
                action_id="file.create",
                parameters={"file_path": target, "code": '{"injected": true}\n'},
                order=0,
            ),
            [target],
        ),
    )

    assert _intent_snapshot(repo) == before, "nothing under .intent/ may change"
    assert core_context.git_service.get_current_commit() == baseline
    row = await _proposal_row(proposal_id)
    assert row["status"] == "failed"
    assert row["consequence_recorded_at"] is None
    # The refusal must be the guard's own hard invariant, not some other
    # failure that merely mentions the path.
    evidence = f"{row.get('failure_reason')} {row.get('execution_results')}"
    assert "Writes to .intent/ are constitutionally prohibited" in evidence, evidence
    reported = await _run_complete_entry(proposal_id)
    assert reported is not None and reported["lifecycle_status"] == "failed"
