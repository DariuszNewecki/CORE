# tests/body/flows/test_write_false_propagation.py
"""
Tests for the write=False propagation invariant in FlowExecutor.

Constitutional rule: architecture.flows.flow_must_propagate_write_false
(scope: src/body/flows/executor.py)

FlowExecutor MUST propagate the caller-supplied write flag to every step
unchanged. The flag is immutable for the lifetime of a flow execution.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from body.flows.executor import FlowExecutor
from body.flows.registry import FlowStep, StepKind
from shared.action_types import ActionImpact, ActionResult


async def _run_step(
    monkeypatch: pytest.MonkeyPatch,
    write: bool,
    caller_params: dict,
) -> dict:
    """Execute a single step and return the kwargs the action received."""
    captured: dict = {}

    async def fake_execute(self, action_id, **kwargs):
        captured.update(kwargs)
        return ActionResult(
            action_id=action_id,
            ok=True,
            data={},
            impact=ActionImpact.READ_ONLY,
            duration_sec=0.0,
        )

    monkeypatch.setattr(
        "body.atomic.executor.ActionExecutor.execute", fake_execute, raising=True
    )
    executor = FlowExecutor(core_context=MagicMock())
    step = FlowStep(ref_id="test.noop", kind=StepKind.ACTION, consumes=None)
    await executor._execute_step(step, write=write, caller_params=caller_params)
    return captured


# ID: 3a9f1c72-e845-4d08-b361-7f2c8d1e5a94
async def test_write_false_reaches_action(monkeypatch: pytest.MonkeyPatch) -> None:
    """write=False from the caller is forwarded to the action unchanged."""
    received = await _run_step(monkeypatch, write=False, caller_params={})
    assert received["write"] is False


# ID: b4d2e7a3-f916-4c51-9a07-8e3b1d6f2c85
async def test_write_true_reaches_action(monkeypatch: pytest.MonkeyPatch) -> None:
    """write=True from the caller is forwarded to the action unchanged."""
    received = await _run_step(monkeypatch, write=True, caller_params={})
    assert received["write"] is True


# ID: c5e8f1b4-a027-4d62-0b18-9f4c2e7a3d96
async def test_write_false_with_extra_caller_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """write=False propagates correctly when additional caller params are present."""
    received = await _run_step(
        monkeypatch,
        write=False,
        caller_params={"source_file": "src/x.py", "limit": 10},
    )
    assert received["write"] is False
    assert received["source_file"] == "src/x.py"
    assert received["limit"] == 10
