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
from body.flows.result import FlowResult
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


# --- #842 Unit F correction: the genuine adversarial case ------------------
#
# The invariant isn't just "the caller's write value is forwarded" (the
# three tests above) -- it's that a step's own STATIC params cannot
# override the caller's write value. merged_params = {**step.params,
# **filtered_caller} in _execute_step means a step whose *declared*
# params include write=True would collide with the explicit write=write
# kwarg at the dispatch call (executor.execute(step.ref_id, write=write,
# **params) / self.execute(step.ref_id, write=write, **params)) -- a
# duplicate-keyword TypeError, caught by the surrounding except Exception
# and returned as a failed StepResult. Nothing runs with elevated write
# authority. Deliberately not asserting the exact Python error text --
# the failure *shape* (never invoked, fails closed) is the invariant,
# not the specific exception message.


async def test_static_write_true_in_step_params_fails_closed_for_action_and_flow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    action_invoked = {"called": False}
    flow_invoked = {"called": False}

    async def fake_action_execute(self, action_id, **kwargs):
        action_invoked["called"] = True
        return ActionResult(
            action_id=action_id,
            ok=True,
            data={},
            impact=ActionImpact.READ_ONLY,
            duration_sec=0.0,
        )

    async def fake_flow_execute(self, flow_id, **kwargs):
        flow_invoked["called"] = True
        return FlowResult(flow_id=flow_id, ok=True, steps=[], duration_sec=0.0)

    monkeypatch.setattr(
        "body.atomic.executor.ActionExecutor.execute", fake_action_execute, raising=True
    )
    monkeypatch.setattr(
        "body.flows.executor.FlowExecutor.execute", fake_flow_execute, raising=True
    )

    executor = FlowExecutor(core_context=MagicMock())

    action_step = FlowStep(
        ref_id="test.noop", kind=StepKind.ACTION, params={"write": True}, consumes=None
    )
    action_result = await executor._execute_step(
        action_step, write=False, caller_params={}
    )

    flow_step = FlowStep(
        ref_id="test.nested_flow",
        kind=StepKind.FLOW,
        params={"write": True},
        consumes=None,
    )
    flow_result = await executor._execute_step(flow_step, write=False, caller_params={})

    assert action_invoked["called"] is False, (
        "action must never be invoked when a step's static params attempt "
        "to override the caller's write=False"
    )
    assert action_result.ok is False

    assert flow_invoked["called"] is False, (
        "nested flow must never be invoked when a step's static params "
        "attempt to override the caller's write=False"
    )
    assert flow_result.ok is False


async def test_write_false_reaches_action_and_nested_flow_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compliant fixture, both step kinds: caller write=False reaches the
    action step (no static override present) and a nested flow step,
    unchanged in both cases."""
    received_write = {"action": None, "flow": None}

    async def fake_action_execute(self, action_id, **kwargs):
        received_write["action"] = kwargs.get("write")
        return ActionResult(
            action_id=action_id,
            ok=True,
            data={},
            impact=ActionImpact.READ_ONLY,
            duration_sec=0.0,
        )

    async def fake_flow_execute(self, flow_id, **kwargs):
        received_write["flow"] = kwargs.get("write")
        return FlowResult(flow_id=flow_id, ok=True, steps=[], duration_sec=0.0)

    monkeypatch.setattr(
        "body.atomic.executor.ActionExecutor.execute", fake_action_execute, raising=True
    )
    monkeypatch.setattr(
        "body.flows.executor.FlowExecutor.execute", fake_flow_execute, raising=True
    )

    executor = FlowExecutor(core_context=MagicMock())

    action_step = FlowStep(ref_id="test.noop", kind=StepKind.ACTION, consumes=None)
    action_result = await executor._execute_step(
        action_step, write=False, caller_params={}
    )

    flow_step = FlowStep(ref_id="test.nested_flow", kind=StepKind.FLOW, consumes=None)
    flow_result = await executor._execute_step(flow_step, write=False, caller_params={})

    assert received_write["action"] is False
    assert action_result.ok is True

    assert received_write["flow"] is False
    assert flow_result.ok is True
