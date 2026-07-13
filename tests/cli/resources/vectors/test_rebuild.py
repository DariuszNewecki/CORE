"""Tests for `core-admin vectors rebuild` (src/cli/resources/vectors/rebuild.py).

Calls the undecorated function directly (`rebuild_vectors.__wrapped__`) to
exercise the rebuild loop's own logic without going through `core_command`'s
interactive-confirmation path. See #777.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import typer

from cli.resources.vectors.rebuild import rebuild_vectors
from shared.action_types import ActionResult


def _ctx(action_executor) -> SimpleNamespace:
    return SimpleNamespace(obj=SimpleNamespace(action_executor=action_executor))


def _code_result(*, status: str, pending_remaining: int = 0, reset_count: int = 0) -> ActionResult:
    return ActionResult(
        action_id="sync.vectors_code",
        ok=True,
        data={
            "status": status,
            "reset_count": reset_count,
            "pending_remaining": pending_remaining,
        },
        duration_sec=0.01,
    )


def _constitution_result(ok: bool = True) -> ActionResult:
    return ActionResult(
        action_id="sync.vectors_constitution",
        ok=ok,
        data={"policies_indexed": 1, "patterns_indexed": 1, "specs_indexed": 1},
        duration_sec=0.01,
    )


async def test_rebuild_vectors_dry_run_calls_both_actions_once():
    executor = AsyncMock()
    executor.execute.side_effect = [
        _code_result(status="dry_run"),
        _constitution_result(),
    ]

    await rebuild_vectors.__wrapped__(_ctx(executor), write=False, yes=False)

    assert executor.execute.await_count == 2
    first_call, second_call = executor.execute.await_args_list
    assert first_call.args[0] == "sync.vectors_code"
    assert first_call.kwargs == {"write": False, "force": True}
    assert second_call.args[0] == "sync.vectors_constitution"
    assert second_call.kwargs == {"write": False}


async def test_rebuild_vectors_write_drains_in_one_pass():
    executor = AsyncMock()
    executor.execute.side_effect = [
        _code_result(status="completed", pending_remaining=0),
        _constitution_result(),
    ]

    await rebuild_vectors.__wrapped__(_ctx(executor), write=True, yes=True)

    assert executor.execute.await_count == 2
    code_call = executor.execute.await_args_list[0]
    assert code_call.kwargs == {"write": True, "force": True}


async def test_rebuild_vectors_write_loops_until_drained():
    executor = AsyncMock()
    executor.execute.side_effect = [
        _code_result(status="partial", pending_remaining=50, reset_count=2460),
        _code_result(status="partial", pending_remaining=10),
        _code_result(status="completed", pending_remaining=0),
        _constitution_result(),
    ]

    await rebuild_vectors.__wrapped__(_ctx(executor), write=True, yes=True)

    assert executor.execute.await_count == 4
    code_calls = executor.execute.await_args_list[:3]
    assert code_calls[0].kwargs == {"write": True, "force": True}
    assert code_calls[1].kwargs == {"write": True, "force": False}
    assert code_calls[2].kwargs == {"write": True, "force": False}
    assert executor.execute.await_args_list[3].args[0] == "sync.vectors_constitution"


async def test_rebuild_vectors_stops_on_code_vectors_failure():
    executor = AsyncMock()
    executor.execute.side_effect = [
        ActionResult(
            action_id="sync.vectors_code",
            ok=False,
            data={"error": "boom"},
            duration_sec=0.01,
        )
    ]

    with pytest.raises(typer.Exit):
        await rebuild_vectors.__wrapped__(_ctx(executor), write=True, yes=True)

    executor.execute.assert_awaited_once()


async def test_rebuild_vectors_stops_on_constitution_failure():
    executor = AsyncMock()
    executor.execute.side_effect = [
        _code_result(status="completed", pending_remaining=0),
        _constitution_result(ok=False),
    ]

    with pytest.raises(typer.Exit):
        await rebuild_vectors.__wrapped__(_ctx(executor), write=True, yes=True)

    assert executor.execute.await_count == 2


async def test_rebuild_vectors_missing_action_executor_exits():
    ctx = SimpleNamespace(obj=SimpleNamespace(action_executor=None))

    with pytest.raises(typer.Exit):
        await rebuild_vectors.__wrapped__(ctx, write=False, yes=False)
