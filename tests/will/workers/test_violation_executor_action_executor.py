"""The LLM remediation route must build its ActionExecutor on a daemon context.

Regression (2026-10-02, daemon journal): ViolationExecutorWorker's ceremony
crashed with ``'NoneType' object has no attribute 'execute'`` at crate
creation. ``CoreContext`` declares ``action_executor`` with a ``None``
default, so the guard ``if not hasattr(ctx, "action_executor")`` never fired
on the context the daemon injects. The same guard sat in CallSiteRewriter.

These tests use a real ``CoreContext`` (not a MagicMock, which would hide
the defect by answering every attribute) with its default ``None`` executor.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.context import CoreContext


def _daemon_context() -> CoreContext:
    ctx = CoreContext(
        registry=MagicMock(),
        git_service=MagicMock(),
        knowledge_service=MagicMock(),
        file_handler=MagicMock(),
        file_service=MagicMock(),
    )
    assert ctx.action_executor is None  # the shape the daemon injects
    return ctx


class _FakeExecutor:
    def __init__(self, ctx: object) -> None:
        self.ctx = ctx
        self.execute = AsyncMock(
            return_value=SimpleNamespace(ok=True, data={"crate_id": "crate-1"})
        )


@pytest.mark.asyncio
async def test_violation_executor_builds_executor_before_the_ceremony() -> None:
    from will.workers.violation_executor import ViolationExecutorWorker

    worker = object.__new__(ViolationExecutorWorker)
    worker._ctx = _daemon_context()
    seen: dict[str, object] = {}

    class _Ceremony:
        def __init__(self, core_context, target_rule, blackboard):  # type: ignore[no-untyped-def]
            seen["executor"] = core_context.action_executor

        async def process_file(self, file_path, findings):  # type: ignore[no-untyped-def]
            return True

    finding = {"id": "e1", "payload": {"file_path": "src/x.py", "rule": "r.one"}}
    with (
        patch("body.atomic.executor.ActionExecutor", _FakeExecutor),
        patch("will.remediation.RemediationCeremony", _Ceremony),
        patch("will.remediation.WorkerRemediationBlackboard", MagicMock()),
    ):
        ok, rules = await worker._process_file("src/x.py", [finding], set())

    assert ok is True and rules == ["r.one"]
    assert isinstance(seen["executor"], _FakeExecutor)
    assert worker._ctx.action_executor is seen["executor"]


@pytest.mark.asyncio
async def test_call_site_rewriter_builds_executor_before_packing_a_crate() -> None:
    from body.workers.call_site_rewriter import CallSiteRewriter

    worker = object.__new__(CallSiteRewriter)
    worker._ctx = _daemon_context()

    with patch("body.atomic.executor.ActionExecutor", _FakeExecutor):
        crate_id = await worker._pack_crate("src/x.py", "print('x')\n")

    assert crate_id == "crate-1"
    assert isinstance(worker._ctx.action_executor, _FakeExecutor)
