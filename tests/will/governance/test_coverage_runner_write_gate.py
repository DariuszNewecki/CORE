# tests/will/governance/test_coverage_runner_write_gate.py

"""#809: coverage_runner's write=false fail-closed guard.

The route layer (api.v1.coverage_routes) already rejects write=false
before dispatch, but run_and_persist_coverage_generation/batch accept
`write` as part of their own signature — a direct or future caller that
bypasses the route must not have the flag silently disregarded, since
neither remediate_file_by_symbol() nor remediate_batch_by_symbol()
(will.self_healing.symbol_coverage_remediation, #814) has a dry-run
contract — each writes unconditionally. These tests pin the runner-level
guard independent of the route.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from will.governance.coverage_runner import (
    _WRITE_FALSE_UNSUPPORTED,
    run_and_persist_coverage_batch,
    run_and_persist_coverage_generation,
)


async def test_generation_write_false_fails_closed_without_remediating():
    context = MagicMock()
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    run_id = uuid4()

    await run_and_persist_coverage_generation(
        context,
        session,
        run_id=run_id,
        target_file="src/foo/bar.py",
        write=False,
    )

    # Two status updates only: "executing" then "failed" — remediation
    # (which would require context.git_service/cognitive_service) never ran.
    assert session.execute.await_count == 2
    last_params = session.execute.await_args_list[-1].args[1]
    assert last_params["status"] == "failed"
    assert last_params["err"] == _WRITE_FALSE_UNSUPPORTED
    context.git_service.repo_path.__truediv__.assert_not_called()


async def test_batch_write_false_fails_closed_without_remediating():
    context = MagicMock()
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    run_id = uuid4()

    await run_and_persist_coverage_batch(
        context,
        session,
        run_id=run_id,
        batch_priority="all",
        write=False,
    )

    assert session.execute.await_count == 2
    last_params = session.execute.await_args_list[-1].args[1]
    assert last_params["status"] == "failed"
    assert last_params["err"] == _WRITE_FALSE_UNSUPPORTED
