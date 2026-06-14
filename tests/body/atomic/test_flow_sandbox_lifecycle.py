"""ADR-106: flow proposals execute in one hermetic worktree.

The flow-granularity counterpart to test_executor_worktree_isolation.py.
Covers the new `SandboxLifecycle.build_flow_execution_context` gate and the
`_flow_has_sandboxable_step` D5 resolver. The worktree-creation + copy-back
primitives are shared with the per-action path (`_make_scoped_context`,
`propagate_changes`) and are exercised there; the full flow-in-worktree +
pytest-in-worktree path is an integration concern verified post-deploy via a
live `flow.build_tests` proposal (ADR-106 "Verification").
"""

from __future__ import annotations

import inspect
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Import for its registration side effect — populates the action registry so
# the D5 resolver can read step impacts. flow_registry auto-loads on .get().
import body.atomic  # noqa: F401
from body.atomic.sandbox_lifecycle import (
    SandboxLifecycle,
    _flow_has_sandboxable_step,
)
from shared.context import CoreContext
from shared.infrastructure.git_service import GitService
from shared.infrastructure.storage.file_handler import FileHandler


def _run(args: list[str], cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Real git repo with one committed file and an empty .intent/."""
    _run(["git", "init"], tmp_path)
    _run(["git", "config", "user.email", "exec@test.local"], tmp_path)
    _run(["git", "config", "user.name", "Exec Test"], tmp_path)
    _run(["git", "config", "commit.gpgsign", "false"], tmp_path)
    (tmp_path / ".intent").mkdir()
    (tmp_path / "scope.py").write_text("# original\n")
    _run(["git", "add", "-A"], tmp_path)
    _run(["git", "commit", "-m", "initial"], tmp_path)
    return tmp_path


def _make_sandbox(repo: Path) -> tuple[SandboxLifecycle, CoreContext]:
    ctx = CoreContext(registry=MagicMock(), git_service=GitService(repo))
    ctx.file_handler = FileHandler(str(repo))
    return SandboxLifecycle(ctx), ctx


# ---- D5 resolver: _flow_has_sandboxable_step --------------------------------


# ID: 1f9c4e72-6a3d-4b58-90e1-2c7f8d4a6b13
def test_build_tests_flow_is_sandboxable() -> None:
    """flow.build_tests writes code (build.tests = WRITE_CODE), so it must
    resolve as sandboxable — the condition that makes its proposals run in a
    worktree."""
    assert _flow_has_sandboxable_step("flow.build_tests") is True


# ID: 8a2d6f31-4c97-4e05-b1a8-5d3e9c7f2b40
def test_unknown_flow_is_not_sandboxable() -> None:
    """An unresolvable flow fails closed to not-sandboxable — no worktree is
    created for a flow that writes nothing."""
    assert _flow_has_sandboxable_step("flow.does_not_exist") is False


# ---- build_flow_execution_context gate --------------------------------------


# ID: 3e7b1a94-2d68-4f53-a0c6-9b4f8e2d7c15
def test_sandboxes_write_bearing_flow(repo: Path) -> None:
    """All gate conditions met → a scoped context on a fresh worktree."""
    sandbox, ctx = _make_sandbox(repo)
    sha = ctx.git_service.get_current_commit()
    scoped_ctx, scoped_git = sandbox.build_flow_execution_context(
        "flow.build_tests", write=True, pre_execution_sha=sha
    )
    try:
        assert scoped_git is not None
        assert scoped_ctx is not ctx
        assert scoped_ctx.git_service is scoped_git
        assert Path(scoped_ctx.file_handler.repo_path) == Path(scoped_git.repo_path)
        assert scoped_git.get_current_commit() == sha
    finally:
        if scoped_git is not None:
            scoped_git.cleanup()


# ID: 6c0f8e23-9a17-4d54-b8e2-1f5a3c9d7b48
def test_passthrough_when_pre_execution_sha_is_none(repo: Path) -> None:
    sandbox, ctx = _make_sandbox(repo)
    scoped_ctx, scoped_git = sandbox.build_flow_execution_context(
        "flow.build_tests", write=True, pre_execution_sha=None
    )
    assert scoped_ctx is ctx
    assert scoped_git is None


# ID: 9d4a2f86-3b71-4e09-a5c8-7e2b6f4d1a93
def test_passthrough_when_write_is_false(repo: Path) -> None:
    sandbox, ctx = _make_sandbox(repo)
    sha = ctx.git_service.get_current_commit()
    scoped_ctx, scoped_git = sandbox.build_flow_execution_context(
        "flow.build_tests", write=False, pre_execution_sha=sha
    )
    assert scoped_ctx is ctx
    assert scoped_git is None


# ID: 2b7e9c44-5d38-4a16-b0f9-3c8a5e2d7f61
def test_passthrough_when_flow_not_sandboxable(repo: Path) -> None:
    """A flow with no write-bearing step (here: unresolvable) passes through
    even when sha + write are set — no needless worktree."""
    sandbox, ctx = _make_sandbox(repo)
    sha = ctx.git_service.get_current_commit()
    scoped_ctx, scoped_git = sandbox.build_flow_execution_context(
        "flow.does_not_exist", write=True, pre_execution_sha=sha
    )
    assert scoped_ctx is ctx
    assert scoped_git is None


# ---- Wiring smoke: proposal_executor flow branch ----------------------------


# ID: 7f3c1e95-8a26-4b40-9d57-2e6b4f8a3c19
def test_proposal_executor_sandboxes_flow_branch() -> None:
    """Source-level wiring guard (matches the per-action ADR-071 smoke style).

    Guards against a refactor that detaches flow execution from the sandbox,
    the production-set stamp, or the worktree cleanup.
    """
    from will.autonomy import proposal_executor as pe

    source = inspect.getsource(pe)
    assert "build_flow_execution_context(" in source, (
        "ADR-106 D1: flow branch must build a flow sandbox context"
    )
    assert "propagate_changes(" in source, (
        "ADR-106 D2: flow success must propagate the production set"
    )
    assert "_sandbox_target_paths" in source, (
        "ADR-106 D2: flow production set must be stamped so compute_production_set "
        "drives the commit set (ADR-101 D2)"
    )
    assert "scoped_git.cleanup()" in source, (
        "ADR-106 D3: the flow worktree must be cleaned up in a finally block"
    )


# ---- run_tests repo-root threading (validate inside the worktree) -----------


# ID: 4a8d2c67-1f59-4e03-b6a1-9c5e3f7d2b84
def test_run_tests_accepts_repo_root_override() -> None:
    """ADR-106 D1 impl note: run_tests must accept a repo_root so a sandboxed
    test.sandbox_validate runs pytest inside the worktree where the generated
    test lives — not the main tree."""
    from shared.infrastructure.validation.test_runner import run_tests

    params = inspect.signature(run_tests).parameters
    assert "repo_root" in params
    assert params["repo_root"].default is None


# ID: 5e9b3d18-7c42-4a06-90f5-2d6a8c4e1b97
def test_sandbox_validate_threads_scoped_repo_root() -> None:
    """test.sandbox_validate accepts the scoped core_context and threads its
    worktree repo_path into run_tests."""
    from body.atomic import test_actions

    params = inspect.signature(test_actions.action_test_sandbox_validate).parameters
    assert "core_context" in params

    source = inspect.getsource(test_actions)
    assert "git_service.repo_path" in source
    assert "repo_root=repo_root" in source


# ---- ADR-107: flow commit set is declared production -----------------------


# ID: 8d2f4a91-6c37-4b50-a1e8-3f9d7c2e5b64
def test_propagate_only_paths_discards_incidental_churn(repo: Path) -> None:
    """ADR-107 D3: propagate_changes(only_paths=...) copies only the declared
    output; an incidental change to another file (the fix.format blast-radius
    shape) stays sandbox-local and never reaches the main tree.

    Uses two committed .py files (both pass the main-repo IntentGuard the
    scoped FileHandler reuses): scope.py is the declared output, other.py is
    the incidental churn.
    """
    (repo / "other.py").write_text("# other original\n")
    _run(["git", "add", "other.py"], repo)
    _run(["git", "commit", "-m", "add other"], repo)

    sandbox, ctx = _make_sandbox(repo)
    sha = ctx.git_service.get_current_commit()
    _scoped_ctx, scoped_git = sandbox.build_flow_execution_context(
        "flow.build_tests", write=True, pre_execution_sha=sha
    )
    try:
        wt = Path(scoped_git.repo_path)
        (wt / "scope.py").write_text("# DECLARED OUTPUT\n")  # declared
        (wt / "other.py").write_text("# INCIDENTAL REFORMAT\n")  # incidental churn

        propagated = sandbox.propagate_changes(scoped_git, only_paths={"scope.py"})

        assert propagated == {"scope.py"}
        # Declared output reached main ...
        assert (repo / "scope.py").read_text() == "# DECLARED OUTPUT\n"
        # ... incidental churn did NOT — main still has the original bytes.
        assert (repo / "other.py").read_text() == "# other original\n"
    finally:
        if scoped_git is not None:
            scoped_git.cleanup()


# ID: 1a7e3c95-4d68-4f02-b9a1-6c5e2d8f4b37
def test_declared_production_unions_files_produced() -> None:
    """ADR-107 D1: the flow production set is the union of steps' files_produced."""
    from body.flows.result import FlowResult, StepResult
    from will.autonomy.proposal_executor import _declared_production

    fr = FlowResult(
        flow_id="flow.build_tests",
        ok=True,
        steps=[
            StepResult(
                ref_id="build.tests",
                required=True,
                ok=True,
                data={
                    "test_file": "tests/x/test_generated.py",
                    "files_produced": ["tests/x/test_generated.py"],
                },
            ),
            StepResult(
                ref_id="fix.format", required=False, ok=True, data={"formatted": True}
            ),
        ],
    )
    assert _declared_production(fr) == {"tests/x/test_generated.py"}


# ID: 6b9d2f47-8a13-4e56-90c2-1f7a5e3d8b09
def test_declared_production_none_when_no_step_declares() -> None:
    """ADR-107 D4: a flow whose steps declare no files_produced returns None so
    propagate falls back to the full worktree diff (un-migrated flows)."""
    from body.flows.result import FlowResult, StepResult
    from will.autonomy.proposal_executor import _declared_production

    fr = FlowResult(
        flow_id="flow.legacy",
        ok=True,
        steps=[
            StepResult(ref_id="some.fix", required=False, ok=True, data={"ok": True}),
            StepResult(
                ref_id="test.sandbox_validate",
                required=True,
                ok=True,
                data={"summary": "ok"},
            ),
        ],
    )
    assert _declared_production(fr) is None


# ID: 3f8c1e74-9b25-4a60-b8d3-5e2a7c9f4d18
def test_build_tests_declares_files_produced_on_write() -> None:
    """ADR-107 D2: build.tests declares its single authored file as
    files_produced (only on write — a dry-run authors nothing)."""
    from body.atomic import build_tests_action

    source = inspect.getsource(build_tests_action)
    assert "files_produced" in source
    assert "[test_file] if write else []" in source


# ID: 9c4a6e23-1d87-4b59-a0f6-2e8b5d3c7f41
def test_proposal_executor_passes_declared_production_to_propagate() -> None:
    """ADR-107 D3 wiring: the flow branch derives the declared production and
    passes it as the propagate allowlist."""
    from will.autonomy import proposal_executor as pe

    source = inspect.getsource(pe)
    assert "_declared_production(" in source, (
        "ADR-107 D1/D3: flow branch must derive the declared production set"
    )
    assert "only_paths=" in source, (
        "ADR-107 D3: declared production must be passed as the propagate allowlist"
    )
