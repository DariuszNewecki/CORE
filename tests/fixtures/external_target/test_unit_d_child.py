"""Focused tests for unit_d_child.py's own worker-invocation logic.

Scaffold correction (2026-09-07): unit_d_child.py previously called
worker.run() directly, skipping Worker._register() and failing the
worker's first blackboard write against the worker_registry foreign key.
The fix replaces that with worker.start() -- the constitutional one-shot
entry point that registers, then runs -- via the extracted
_run_worker_once() helper below.

These tests exercise _run_worker_once() in isolation against a stub
worker object, proving the invocation contract without provisioning a
database or running the full governed scenario (that remains the live
run, executed once, against real components -- see the Unit D reports).
"""

from __future__ import annotations

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))

from unit_d_child import _run_worker_once


class _StubWorker:
    """Mimics Worker.start()'s contract: register(), then run().

    Records call order so tests can assert registration happens before
    execution, and that start() -- never run() directly -- is what this
    scaffold invokes.
    """

    def __init__(self, *, fail: bool = False) -> None:
        self.calls: list[str] = []
        self._fail = fail

    async def start(self) -> None:
        self.calls.append("register")
        self.calls.append("run")
        if self._fail:
            raise RuntimeError("boom: worker failed inside start()")


class TestRunWorkerOnceSuccess:
    async def test_registration_precedes_execution(self) -> None:
        worker = _StubWorker()
        result = await _run_worker_once(
            worker,
            proposal_id="p-1",
            pre_approval_status="draft",
            final_status="approved",
        )
        assert result is None
        assert worker.calls == ["register", "run"]

    async def test_start_is_called_exactly_once(self) -> None:
        worker = _StubWorker()
        await _run_worker_once(
            worker,
            proposal_id="p-1",
            pre_approval_status="draft",
            final_status="approved",
        )
        assert worker.calls.count("run") == 1
        assert worker.calls.count("register") == 1

    async def test_does_not_invoke_run_directly(self) -> None:
        # A stub exposing only start() (no bare run()) must still satisfy
        # _run_worker_once -- proving it never reaches for worker.run().
        worker = _StubWorker()
        assert not hasattr(worker, "run")
        result = await _run_worker_once(
            worker,
            proposal_id="p-1",
            pre_approval_status="draft",
            final_status="approved",
        )
        assert result is None


class TestRunWorkerOnceFailure:
    async def test_start_failure_is_labeled_worker_start(self) -> None:
        worker = _StubWorker(fail=True)
        result = await _run_worker_once(
            worker,
            proposal_id="p-2",
            pre_approval_status="draft",
            final_status="approved",
        )
        assert result is not None
        assert result["ok"] is False
        assert result["stage"] == "worker_start"
        assert result["stage"] != "unhandled_exception"

    async def test_proposal_id_survives_failure_reporting(self) -> None:
        worker = _StubWorker(fail=True)
        result = await _run_worker_once(
            worker,
            proposal_id="p-survives-123",
            pre_approval_status="draft",
            final_status="approved",
        )
        assert result is not None
        assert result["proposal_id"] == "p-survives-123"

    async def test_lifecycle_status_survives_failure_reporting(self) -> None:
        worker = _StubWorker(fail=True)
        result = await _run_worker_once(
            worker,
            proposal_id="p-2",
            pre_approval_status="draft",
            final_status="approved",
        )
        assert result is not None
        assert result["pre_approval_status"] == "draft"
        assert result["final_status"] == "approved"

    async def test_error_text_is_preserved(self) -> None:
        worker = _StubWorker(fail=True)
        result = await _run_worker_once(
            worker,
            proposal_id="p-2",
            pre_approval_status="draft",
            final_status="approved",
        )
        assert result is not None
        assert "boom: worker failed inside start()" in result["error"]

    async def test_registration_still_recorded_before_the_failure(self) -> None:
        # The stub's start() appends "register" before raising, mirroring
        # the real Worker.start() calling _register() before run() can
        # fail -- registration is not skipped just because run() errors.
        worker = _StubWorker(fail=True)
        await _run_worker_once(
            worker,
            proposal_id="p-2",
            pre_approval_status="draft",
            final_status="approved",
        )
        assert "register" in worker.calls
