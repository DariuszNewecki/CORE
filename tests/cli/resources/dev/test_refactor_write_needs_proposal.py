"""`core-admin dev refactor --write` writes only through a governor-approved
Proposal (ADR-160 D3), the same path as POST /develop/goal: with no approved
Proposal, --write is refused its direct write and records a pending one."""

from __future__ import annotations

import inspect
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from cli.resources.dev import refactor
from shared.models.workflow_models import PhaseResult, PhaseWorkflowResult
from will.autonomy.autonomous_developer import _GRANDFATHERED_DIRECT_WRITE_CALLERS


def _worker() -> MagicMock:
    worker = MagicMock()
    worker.start = AsyncMock()
    worker.result = PhaseWorkflowResult(
        ok=True, phase_results=[PhaseResult(name="create_proposal", ok=True)]
    )
    worker.run_id = "rid-1"
    worker.proposal_id = "proposal-1"
    worker.proposal_approval_required = True
    worker.unavailable_reason = None
    worker.probe_records = []
    return worker


@asynccontextmanager
async def _session():
    yield MagicMock()


async def _run(write: bool) -> tuple[MagicMock, MagicMock]:
    config = MagicMock()
    config.get_bool = AsyncMock(return_value=True)
    ctx = MagicMock()
    command = inspect.unwrap(refactor.dev_refactor_cmd)
    out = MagicMock()
    with (
        patch.object(refactor, "load_dotenv", MagicMock()),
        patch.object(refactor, "get_session", _session),
        patch.object(refactor.ConfigService, "create", AsyncMock(return_value=config)),
        patch.object(refactor, "console", out),
        patch(
            "will.autonomy.autonomous_developer.GoalExecutionWorker",
            return_value=_worker(),
        ) as worker_cls,
    ):
        await command(
            ctx,
            goal="Improve modularity of x.py",
            write=write,
            workflow="refactor_modularity",
        )
    return worker_cls, out


# ID: {U1}
async def test_write_without_an_approved_proposal_only_records_one() -> None:
    worker_cls, out = await _run(write=True)

    _, kwargs = worker_cls.call_args
    assert kwargs["write"] is True
    assert kwargs["create_proposal_only"] is True
    printed = " ".join(str(c.args[0]) for c in out.print.call_args_list if c.args)
    assert "proposal-1" in printed and "pending Governor approval" in printed


# ID: {U2}
def test_dev_refactor_is_no_longer_grandfathered_onto_direct_writes() -> None:
    assert "cli.resources.dev.refactor" not in _GRANDFATHERED_DIRECT_WRITE_CALLERS


# ID: 7d965d45-3912-45dc-a410-aea35e01fb0b
async def test_dry_run_stays_a_dry_run() -> None:
    worker_cls, _ = await _run(write=False)
    _, kwargs = worker_cls.call_args
    assert kwargs["write"] is False and kwargs["create_proposal_only"] is False
