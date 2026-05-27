"""Phase 3 (ADR-071 D2.2): executor worktree-sandbox isolation tests.

Verifies the b11f4dba race shape is architecturally closed:
- Without the sandbox gate met, execution passes through to the main tree.
- When sandboxed, action writes land in /tmp/core-action-sandbox-<uuid>/
  and only reach main on clean propagation.
- If the main tree has uncommitted edits in the sandbox's target paths
  (concurrent governor edit), propagation refuses with a loud RuntimeError
  rather than silently overwriting governor work.
"""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from body.atomic.executor import ActionExecutor
from body.atomic.registry import ActionCategory, ActionDefinition
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import ActionMetadata
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


def _make_context(repo: Path) -> CoreContext:
    ctx = CoreContext(registry=MagicMock())
    ctx.git_service = GitService(repo)
    ctx.file_handler = FileHandler(str(repo))
    return ctx


def _bare_executor(repo: Path) -> tuple[ActionExecutor, CoreContext]:
    """Construct an ActionExecutor without running the registry-priming
    __init__ — these tests only exercise the new sandbox methods."""
    executor = ActionExecutor.__new__(ActionExecutor)
    ctx = _make_context(repo)
    executor.core_context = ctx
    executor.registry = MagicMock()
    return executor, ctx


def _write_action(write: bool = False, core_context=None, **kwargs) -> ActionResult:
    """Test fixture action: writes to scope.py under whatever repo the
    file_handler is bound to. Bypasses FileHandler's write_runtime_text
    so it doesn't hit IntentGuard during these unit-level tests — tests/
    is excluded from no_direct_writes."""
    target = core_context.file_handler.repo_path / "scope.py"
    target.write_text("# action wrote this\n")
    return ActionResult(
        action_id="test.sandbox_write",
        ok=True,
        data={"path": "scope.py"},
        duration_sec=0.0,
    )


def _attach_metadata(fn, impact: ActionImpact) -> None:
    fn._atomic_action_metadata = ActionMetadata(
        action_id="test.sandbox_write",
        intent="test fixture",
        impact=impact,
        policies=[],
    )


def _make_definition(
    impact: ActionImpact = ActionImpact.WRITE_CODE,
) -> ActionDefinition:
    async def executor(
        write: bool = False, core_context=None, **kwargs
    ) -> ActionResult:
        return _write_action(write=write, core_context=core_context, **kwargs)

    _attach_metadata(executor, impact)
    return ActionDefinition(
        action_id="test.sandbox_write",
        description="test",
        category=ActionCategory.FIX,
        policies=[],
        executor=executor,
        impact_level="moderate",
    )


# ---- _build_execution_context gate -----------------------------------------


def test_sandboxes_when_sha_write_and_impact_match(repo: Path) -> None:
    executor, ctx = _bare_executor(repo)
    sha = ctx.git_service.get_current_commit()
    defn = _make_definition(ActionImpact.WRITE_CODE)

    scoped_ctx, scoped_git = executor._build_execution_context(
        defn, write=True, pre_execution_sha=sha
    )
    try:
        assert scoped_git is not None
        assert scoped_ctx is not ctx
        assert scoped_ctx.git_service is scoped_git
        assert scoped_ctx.file_handler is not ctx.file_handler
        assert Path(scoped_ctx.file_handler.repo_path) == Path(scoped_git.repo_path)
        assert scoped_git.get_current_commit() == sha
    finally:
        if scoped_git is not None:
            scoped_git.cleanup()


def test_passthrough_when_pre_execution_sha_is_none(repo: Path) -> None:
    executor, ctx = _bare_executor(repo)
    defn = _make_definition()
    scoped_ctx, scoped_git = executor._build_execution_context(
        defn, write=True, pre_execution_sha=None
    )
    assert scoped_ctx is ctx
    assert scoped_git is None


def test_passthrough_when_write_is_false(repo: Path) -> None:
    executor, ctx = _bare_executor(repo)
    sha = ctx.git_service.get_current_commit()
    defn = _make_definition()
    scoped_ctx, scoped_git = executor._build_execution_context(
        defn, write=False, pre_execution_sha=sha
    )
    assert scoped_ctx is ctx
    assert scoped_git is None


def test_passthrough_when_impact_is_read_only(repo: Path) -> None:
    executor, ctx = _bare_executor(repo)
    sha = ctx.git_service.get_current_commit()
    defn = _make_definition(ActionImpact.READ_ONLY)
    scoped_ctx, scoped_git = executor._build_execution_context(
        defn, write=True, pre_execution_sha=sha
    )
    assert scoped_ctx is ctx
    assert scoped_git is None


def test_passthrough_when_impact_is_write_data(repo: Path) -> None:
    """WRITE_DATA targets DBs / external systems, not the source tree."""
    executor, ctx = _bare_executor(repo)
    sha = ctx.git_service.get_current_commit()
    defn = _make_definition(ActionImpact.WRITE_DATA)
    scoped_ctx, scoped_git = executor._build_execution_context(
        defn, write=True, pre_execution_sha=sha
    )
    assert scoped_ctx is ctx
    assert scoped_git is None


# ---- _propagate_sandbox_changes copy + conflict-check ---------------------


def test_clean_propagation_copies_sandbox_writes_to_main(repo: Path) -> None:
    executor, ctx = _bare_executor(repo)
    sha = ctx.git_service.get_current_commit()
    defn = _make_definition()

    scoped_ctx, scoped_git = executor._build_execution_context(
        defn, write=True, pre_execution_sha=sha
    )
    try:
        asyncio.run(defn.executor(write=True, core_context=scoped_ctx))
        # Sandbox mutated; main untouched
        assert (
            Path(scoped_git.repo_path) / "scope.py"
        ).read_text() == "# action wrote this\n"
        assert (repo / "scope.py").read_text() == "# original\n"

        executor._propagate_sandbox_changes(scoped_git)

        # Main now reflects sandbox content
        assert (repo / "scope.py").read_text() == "# action wrote this\n"
    finally:
        if scoped_git is not None:
            scoped_git.cleanup()


def test_propagation_refuses_when_main_has_concurrent_edit_on_target(
    repo: Path,
) -> None:
    """The b11f4dba race shape: governor edits the same file the worker is
    sandbox-editing. Sandbox propagation must refuse, not overwrite."""
    executor, ctx = _bare_executor(repo)
    sha = ctx.git_service.get_current_commit()
    defn = _make_definition()

    scoped_ctx, scoped_git = executor._build_execution_context(
        defn, write=True, pre_execution_sha=sha
    )
    try:
        # Simulate concurrent governor edit on main tree
        (repo / "scope.py").write_text("# GOVERNOR EDIT\n")

        # Action runs in sandbox (sees pre-edit state)
        asyncio.run(defn.executor(write=True, core_context=scoped_ctx))

        # Sandbox has worker's content; main still has governor's edit
        assert (
            Path(scoped_git.repo_path) / "scope.py"
        ).read_text() == "# action wrote this\n"
        assert (repo / "scope.py").read_text() == "# GOVERNOR EDIT\n"

        with pytest.raises(RuntimeError, match=r"ADR-071 D2\.2"):
            executor._propagate_sandbox_changes(scoped_git)

        # Governor's edit survives the refused propagation
        assert (repo / "scope.py").read_text() == "# GOVERNOR EDIT\n"
    finally:
        if scoped_git is not None:
            scoped_git.cleanup()


def test_propagation_proceeds_when_governor_edits_a_different_file(repo: Path) -> None:
    """Governor edit on a non-target path is not a conflict — propagation
    proceeds for the worker's file and the governor's file stays untouched."""
    executor, ctx = _bare_executor(repo)
    # Add a second file the governor will edit
    (repo / "other.py").write_text("# other original\n")
    _run(["git", "add", "other.py"], repo)
    _run(["git", "commit", "-m", "add other"], repo)
    sha = ctx.git_service.get_current_commit()
    defn = _make_definition()

    scoped_ctx, scoped_git = executor._build_execution_context(
        defn, write=True, pre_execution_sha=sha
    )
    try:
        # Governor edits other.py (NOT the worker's target)
        (repo / "other.py").write_text("# GOVERNOR EDIT TO OTHER\n")

        asyncio.run(defn.executor(write=True, core_context=scoped_ctx))
        executor._propagate_sandbox_changes(scoped_git)

        # Worker's file propagated; governor's file untouched
        assert (repo / "scope.py").read_text() == "# action wrote this\n"
        assert (repo / "other.py").read_text() == "# GOVERNOR EDIT TO OTHER\n"
    finally:
        if scoped_git is not None:
            scoped_git.cleanup()


def test_propagation_no_op_when_sandbox_made_no_changes(repo: Path) -> None:
    executor, ctx = _bare_executor(repo)
    sha = ctx.git_service.get_current_commit()
    defn = _make_definition()
    _, scoped_git = executor._build_execution_context(
        defn, write=True, pre_execution_sha=sha
    )
    try:
        # No action invocation — sandbox stays clean
        executor._propagate_sandbox_changes(scoped_git)
        assert (repo / "scope.py").read_text() == "# original\n"
    finally:
        if scoped_git is not None:
            scoped_git.cleanup()


# ---- Wiring smoke: pre_execution_sha plumbing through ProposalExecutor ----


def test_proposal_executor_threads_pre_execution_sha_into_action_executor() -> None:
    """Wiring smoke (ADR-071 D2.2 Phase 2).

    The same pattern as test_proposal_executor_results_keying: source-review
    is the authoritative check on the executor's wiring. This guards
    against a refactor that detaches the sandbox SHA from the action call.
    """
    import inspect

    from will.autonomy import proposal_executor as pe

    source = inspect.getsource(pe)

    # The SHA must be captured before the action loop ...
    assert "pre_execution_sha = capture_git_sha(" in source, (
        "ADR-071 D2.2: pre_execution_sha capture site missing from proposal_executor"
    )
    # ... and threaded through into action_executor.execute(...).
    assert "pre_execution_sha=pre_execution_sha" in source, (
        "ADR-071 D2.2: pre_execution_sha not threaded into action_executor.execute"
    )

    # The executor side must accept it as a named parameter.
    from body.atomic.executor import ActionExecutor

    sig = inspect.signature(ActionExecutor.execute)
    assert "pre_execution_sha" in sig.parameters, (
        "ADR-071 D2.2: ActionExecutor.execute is missing pre_execution_sha"
    )
    assert sig.parameters["pre_execution_sha"].default is None, (
        "ADR-071 D2.2: pre_execution_sha default must be None for CLI passthrough"
    )
