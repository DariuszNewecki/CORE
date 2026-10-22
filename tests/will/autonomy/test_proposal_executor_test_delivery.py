# tests/will/autonomy/test_proposal_executor_test_delivery.py
"""ProposalExecutor commits a generated test to CORE's delivery branch, not
onto the clone's HEAD (2026-10-20: 109 test commits on ``develop`` diverged
the clone from upstream and had to be rescued by hand).

A real clone on ``develop`` and real sandbox worktrees; the flow itself (the
LLM and the sandbox test run) is a stand-in that writes one test file, and
the database collaborators are mocked.
"""

from __future__ import annotations

import subprocess
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.infrastructure.git_service import GitService
from will.autonomy.proposal import ProposalAction, ProposalStatus
from will.autonomy.proposal_executor import ProposalExecutor


TEST_FILE = "tests/test_a.py"
DELIVERY_REF = "refs/heads/core/test-gen"


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.fixture
def clone(tmp_path: Path) -> Path:
    up = tmp_path / "upstream"
    up.mkdir()
    _git(up, "init", "-q", "-b", "main")
    (up / ".gitignore").write_text("var/\n")
    (up / "src").mkdir()
    (up / "src/a.py").write_text("def a():\n    return 1\n")
    _git(up, "add", "-A")
    _git(up, "commit", "-q", "-m", "base")
    _git(tmp_path, "clone", "-q", "-b", "main", str(up), "clone")
    repo = tmp_path / "clone"
    _git(repo, "checkout", "-q", "-b", "develop")
    return repo


class _Sandbox:
    """SandboxLifecycle with real worktrees; propagation must never run."""

    def __init__(self, core_context: object) -> None:
        self.git = core_context.git_service  # type: ignore[attr-defined]

    def build_flow_execution_context(self, flow_id: str, write: bool, base: str):
        scoped = self.git.create_worktree(base)
        return SimpleNamespace(repo_path=scoped.repo_path), scoped

    def propagate_changes(self, *a: object, **k: object) -> set[str]:
        raise AssertionError("a delivered flow must not touch the main tree")


class _Flow:
    """The flow: writes a test into its sandbox and declares it produced."""

    def __init__(self, scoped_context: SimpleNamespace, **_: object) -> None:
        self.root = Path(scoped_context.repo_path)

    async def execute(self, **_: object) -> SimpleNamespace:
        (self.root / "tests").mkdir(exist_ok=True)
        (self.root / TEST_FILE).write_text("def test_a():\n    assert True\n")
        step = SimpleNamespace(data={"files_produced": [TEST_FILE]})
        return SimpleNamespace(ok=True, steps=[step], data={})


@asynccontextmanager
async def _free(*_a: object, **_k: object):
    yield


@asynccontextmanager
async def _session(*_a: object, **_k: object):
    yield AsyncMock()


# ID: 0c5a8e3f-6b2d-4f71-9e4a-3d7b1f8c2e96
async def test_generated_test_lands_on_the_delivery_branch_not_head(
    clone: Path,
) -> None:
    head = _git(clone, "rev-parse", "HEAD")
    proposal = MagicMock()
    proposal.proposal_id = "pid-delivery-1"
    proposal.status = ProposalStatus.APPROVED
    proposal.goal = "Autonomous test generation: src/a.py::a (function)"
    proposal.actions = [
        ProposalAction(
            flow_id="flow.build_test_for_symbol",
            parameters={"source_file": "src/a.py", "symbol_name": "a", "write": True},
        )
    ]
    proposal.provenance.producer = "core:flow.build_test_for_symbol"
    proposal.constitutional_constraints = {}
    proposal.scope = MagicMock(policies=[])

    executor = object.__new__(ProposalExecutor)
    executor.core_context = MagicMock(git_service=GitService(clone))
    executor.action_executor = AsyncMock()
    repo = AsyncMock()
    repo.get = AsyncMock(return_value=proposal)
    commit_on_head = MagicMock()

    with (
        patch("will.autonomy.proposal_executor.async_repo_lock", _free),
        patch("will.autonomy.proposal_executor.service_registry.session", _session),
        # Delivery is under test, not the ADR-172 spend cap (law sets one).
        patch(
            "will.autonomy.proposal_executor.refuse_when_daily_spend_cap_reached",
            AsyncMock(),
        ),
        patch(
            "will.autonomy.proposal_executor.ProposalRepository",
            MagicMock(return_value=repo),
        ),
        patch("will.autonomy.proposal_executor.ProposalStateManager") as states,
        patch("will.autonomy.proposal_executor.SandboxLifecycle", _Sandbox),
        patch("will.autonomy.proposal_executor.FlowExecutor", _Flow),
        patch(
            "will.autonomy.proposal_executor._build_cognitive_delegate",
            MagicMock(return_value=None),
        ),
        patch(
            "will.autonomy.proposal_executor.commit_proposal_changes", commit_on_head
        ),
        patch(
            "will.autonomy.proposal_executor.record_consequence",
            AsyncMock(return_value=True),
        ) as record,
        patch(
            "will.autonomy.proposal_executor.resolve_deferred_findings",
            AsyncMock(return_value=True),
        ),
    ):
        for name in ("mark_failed", "mark_finalizing", "mark_completed"):
            setattr(states.return_value, name, AsyncMock())
        result = await executor.execute(
            "pid-delivery-1", claimed_by=MagicMock(), write=True
        )

    assert result["lifecycle_status"] == "completed", result
    assert _git(clone, "rev-parse", "HEAD") == head
    assert _git(clone, "rev-parse", "refs/heads/develop") == head
    assert _git(clone, "status", "--porcelain", "--untracked-files=all") == ""
    commit_on_head.assert_not_called()

    delivered = _git(clone, "rev-parse", DELIVERY_REF)
    assert _git(clone, "show", f"{DELIVERY_REF}:{TEST_FILE}").startswith("def test_a")
    assert _git(clone, "log", "-1", "--format=%an", DELIVERY_REF) == (
        "core:flow.build_test_for_symbol"
    )
    # The consequence records the delivered commit itself.
    kwargs = record.await_args.kwargs
    assert kwargs["post_sha"] == delivered
    assert kwargs["pre_sha"] == head
    assert result["post_execution_sha"] == delivered
