# tests/body/atomic/test_executor_physical_containment.py
"""Unit C.1: physical path-containment enforcement (ADR-159 Notes).

Closes the gap Unit C demonstrated: a lexically authorized target such as
``package/link.py`` must not be able to redirect a write outside the
authorized ``package/`` subtree via a symlink. ``_check_physical_
containment`` (``body/atomic/executor.py``) is the last production
enforcement point with both the authoritative bound repository root and a
position before ``definition.executor`` is ever invoked -- see its
docstring for the full rationale.

Two layers of proof:

- ``TestCheckPhysicalContainment`` -- direct, fast tests of the helper
  against real symlinks on a real filesystem (``tmp_path``), with only the
  envelope *data source* mocked (a legitimate, narrow mock of a dependency,
  never a reimplementation of the logic under test).
- ``TestExecutorRefusesBeforeDispatch`` -- the real production pre-dispatch
  path: a genuine ``ActionExecutor.execute()`` call, with a trap executor
  that fails loudly if dispatch is ever reached, proving refusal happens
  strictly before the registered action callable runs.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from body.atomic.executor import ActionExecutor, _check_physical_containment
from body.atomic.registry import ActionCategory, ActionDefinition, ActionRegistry
from shared.action_types import ActionResult


_ENVELOPE = {
    "authorized_actions": frozenset({"fix.format"}),
    "authorized_path_prefixes": ("package/",),
    "authorized_extensions": (".py",),
}


def _ctx(repo_root) -> SimpleNamespace:
    return SimpleNamespace(git_service=SimpleNamespace(repo_path=str(repo_root)))


class _FakeSession:
    """Minimal stand-in supporting `async with session.begin(): await
    session.execute(...)` -- just enough for ActionExecutor._audit_log to
    complete on the success path, without a real database."""

    async def execute(self, *_args, **_kwargs) -> None:
        return None

    def begin(self) -> _FakeSession:
        return self

    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(self, *_exc_info: object) -> bool:
        return False


class _FakeSessionRegistry:
    """Minimal stand-in for CoreContext.registry, supporting only
    `async with core_context.registry.session() as session`."""

    def session(self) -> _FakeSession:
        return _FakeSession()


def _ctx_with_audit(repo_root) -> SimpleNamespace:
    """A context that can complete a full, successful execute() call --
    including step 7's real audit-log write path -- without a database."""
    ctx = _ctx(repo_root)
    ctx.registry = _FakeSessionRegistry()
    return ctx


@pytest.fixture(autouse=True)
def _mock_envelope():
    with patch(
        "body.atomic.executor.load_safe_auto_approval_envelope",
        return_value=dict(_ENVELOPE),
    ):
        yield


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    (root / "package").mkdir(parents=True)
    (root / "package" / "example.py").write_text("x = 1\n")
    (root / "scripts").mkdir()
    (root / "scripts" / "outside.py").write_text("y = 2\n")
    return root


class TestCheckPhysicalContainment:
    def test_normal_file_is_allowed(self, repo) -> None:
        assert _check_physical_containment(_ctx(repo), "package/example.py") is None

    def test_no_file_path_is_a_noop(self, repo) -> None:
        assert _check_physical_containment(_ctx(repo), None) is None

    def test_file_path_outside_every_authorized_prefix_is_a_noop(self, repo) -> None:
        """Out of scope for this property by design: a target this check
        does not recognize as envelope-governed was never relying on the
        envelope for its authorization in the first place (e.g. a
        governor-approved action, which ADR ruling 7 exempts from the
        envelope)."""
        assert _check_physical_containment(_ctx(repo), "scripts/outside.py") is None

    def test_missing_git_service_is_a_noop(self, repo) -> None:
        ctx = SimpleNamespace(git_service=None)
        assert _check_physical_containment(ctx, "package/example.py") is None

    def test_envelope_load_failure_is_a_noop(self, repo) -> None:
        with patch(
            "body.atomic.executor.load_safe_auto_approval_envelope",
            return_value={"_error": True, "reason": "broken"},
        ):
            assert _check_physical_containment(_ctx(repo), "package/example.py") is None

    def test_symlinked_file_pointing_outside_repo_is_denied(self, repo) -> None:
        outside = repo.parent / "outside.py"
        outside.write_text("stolen = True\n")
        (repo / "package" / "link.py").symlink_to(outside)

        reason = _check_physical_containment(_ctx(repo), "package/link.py")
        assert reason is not None
        assert "symbolic link" in reason

    def test_symlinked_directory_leading_outside_is_denied(self, repo) -> None:
        outside_dir = repo.parent / "outside_dir"
        outside_dir.mkdir()
        (outside_dir / "evil.py").write_text("evil = True\n")
        (repo / "package" / "linkdir").symlink_to(outside_dir, target_is_directory=True)

        reason = _check_physical_containment(_ctx(repo), "package/linkdir/evil.py")
        assert reason is not None
        assert "symbolic link" in reason

    def test_symlink_to_another_file_inside_package_is_denied(self, repo) -> None:
        (repo / "package" / "link.py").symlink_to(repo / "package" / "example.py")
        reason = _check_physical_containment(_ctx(repo), "package/link.py")
        assert reason is not None
        assert "symbolic link" in reason

    def test_symlink_to_elsewhere_inside_repo_is_denied(self, repo) -> None:
        (repo / "package" / "link.py").symlink_to(repo / "scripts" / "outside.py")
        reason = _check_physical_containment(_ctx(repo), "package/link.py")
        assert reason is not None
        assert "symbolic link" in reason

    def test_dangling_symlink_is_denied(self, repo) -> None:
        (repo / "package" / "dangling.py").symlink_to(repo.parent / "nope.py")
        reason = _check_physical_containment(_ctx(repo), "package/dangling.py")
        assert reason is not None
        assert "symbolic link" in reason

    def test_symlinked_prefix_directory_is_denied(self, repo) -> None:
        real = repo / "package"
        moved = repo.parent / "package_real"
        real.rename(moved)
        real.symlink_to(moved, target_is_directory=True)

        reason = _check_physical_containment(_ctx(repo), "package/example.py")
        assert reason is not None
        assert "authorized prefix directory is a symbolic link" in reason

    def test_root_never_read_from_cwd_env_or_singleton(
        self, repo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The root comes only from exec_context.git_service.repo_path.
        Point cwd and REPO_PATH somewhere unrelated and confirm the check
        still operates against the real bound root, not either of those."""
        elsewhere = repo.parent / "unrelated"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)
        monkeypatch.setenv("REPO_PATH", str(elsewhere))

        assert _check_physical_containment(_ctx(repo), "package/example.py") is None

        outside = repo.parent / "outside2.py"
        outside.write_text("z = 3\n")
        (repo / "package" / "link2.py").symlink_to(outside)
        reason = _check_physical_containment(_ctx(repo), "package/link2.py")
        assert reason is not None

    def test_nonexistent_target_with_no_symlink_component_is_not_a_violation(
        self, repo
    ) -> None:
        """No symlink anywhere on the path, target simply does not exist
        yet -- not this check's concern (defers to the action's own
        file-existence handling, e.g. fix.format's graceful skip)."""
        assert (
            _check_physical_containment(_ctx(repo), "package/not_created_yet.py")
            is None
        )


class _DispatchReached(AssertionError):
    """Raised by the trap executor if the containment refusal failed to block."""


async def _trap_executor(**_kwargs) -> ActionResult:
    raise _DispatchReached(
        "ActionExecutor invoked the registered action despite a symlink "
        "escape under the authorized prefix. Physical containment refusal "
        "was bypassed."
    )


def _stub_definition() -> ActionDefinition:
    return ActionDefinition(
        action_id="test.containment_refusal",
        description="Unit C.1 refusal-path test fixture",
        category=ActionCategory.FIX,
        policies=[],
        executor=_trap_executor,
        impact_level="safe",
    )


class TestExecutorRefusesBeforeDispatch:
    """The real production pre-dispatch enforcement path: a genuine
    ActionExecutor.execute() call (not only the private helper)."""

    async def test_execute_refuses_before_invoking_the_action(self, repo) -> None:
        (repo / "package" / "link.py").symlink_to(repo.parent / "does-not-exist.py")

        registry = ActionRegistry()
        registry.register(_stub_definition())

        executor = ActionExecutor.__new__(ActionExecutor)
        executor.core_context = _ctx(repo)
        executor.registry = registry
        executor._sandbox = MagicMock()
        executor._sandbox.build_execution_context.return_value = (_ctx(repo), None)

        result = await executor.execute(
            action_id="test.containment_refusal",
            write=True,
            file_path="package/link.py",
        )

        assert result.ok is False, (
            "ActionExecutor must refuse dispatch when the target physically "
            "escapes the authorized prefix via a symlink (ADR-159 Notes, "
            "Unit C.1)."
        )
        assert result.data["error"] == "Physical containment violation"
        assert "symbolic link" in result.data["details"]

    async def test_execute_still_dispatches_a_genuinely_contained_target(
        self, repo
    ) -> None:
        registry = ActionRegistry()

        async def _ok_executor(**_kwargs) -> ActionResult:
            return ActionResult(action_id="test.containment_ok", ok=True, data={})

        registry.register(
            ActionDefinition(
                action_id="test.containment_ok",
                description="control case",
                category=ActionCategory.FIX,
                policies=[],
                executor=_ok_executor,
                impact_level="safe",
            )
        )

        ctx = _ctx_with_audit(repo)
        executor = ActionExecutor.__new__(ActionExecutor)
        executor.core_context = ctx
        executor.registry = registry
        executor._sandbox = MagicMock()
        executor._sandbox.build_execution_context.return_value = (ctx, None)

        result = await executor.execute(
            action_id="test.containment_ok",
            write=True,
            file_path="package/example.py",
        )
        assert result.ok is True

    async def test_refusal_leaves_repository_untouched(self, repo) -> None:
        outside = repo.parent / "canary.py"
        outside.write_text("untouched = True\n")
        (repo / "package" / "link.py").symlink_to(outside)

        registry = ActionRegistry()
        registry.register(_stub_definition())
        executor = ActionExecutor.__new__(ActionExecutor)
        executor.core_context = _ctx(repo)
        executor.registry = registry
        executor._sandbox = MagicMock()
        executor._sandbox.build_execution_context.return_value = (_ctx(repo), None)

        before = outside.read_text()
        result = await executor.execute(
            action_id="test.containment_refusal",
            write=True,
            file_path="package/link.py",
        )
        after = outside.read_text()

        assert result.ok is False
        assert before == after == "untouched = True\n"
