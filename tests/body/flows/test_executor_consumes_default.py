# tests/body/flows/test_executor_consumes_default.py
"""
Tests for FlowExecutor caller-param forwarding semantics (#445).

The default for ``FlowStep.consumes`` was inverted 2026-05-25: absent
``consumes`` now forwards all caller params (was: drop all). These tests
pin the three branches of that contract.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from body.flows.executor import FlowExecutor
from body.flows.registry import FlowStep, StepKind
from shared.action_types import ActionImpact, ActionResult


# ID: 68a93f30-a143-412c-949d-d18e73895abe
async def _invoke(
    monkeypatch: pytest.MonkeyPatch,
    step: FlowStep,
    caller_params: dict[str, object],
) -> dict[str, object]:
    """Run ``_execute_step`` against a mocked ActionExecutor and return the kwargs the action received."""
    captured: dict[str, object] = {}

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
    await executor._execute_step(step, write=False, caller_params=caller_params)
    return captured


# ID: 4889a618-61be-40ef-b974-babbd6c387dc
async def test_consumes_none_forwards_all_caller_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """consumes=None (the new default) — every caller param reaches the action."""
    step = FlowStep(ref_id="test.noop", kind=StepKind.ACTION, consumes=None)
    received = await _invoke(
        monkeypatch, step, {"source_file": "src/x.py", "extra": 42}
    )
    assert received == {"source_file": "src/x.py", "extra": 42, "write": False}


# ID: efbaa29c-6b24-4781-a70d-f6e4f34bf8ed
async def test_consumes_tuple_filters_to_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """consumes=("source_file",) — only source_file reaches the action."""
    step = FlowStep(ref_id="test.noop", kind=StepKind.ACTION, consumes=("source_file",))
    received = await _invoke(
        monkeypatch, step, {"source_file": "src/x.py", "extra": 42}
    )
    assert received == {"source_file": "src/x.py", "write": False}


# ID: 6de4e6e3-6a74-4d80-a0dc-90b823a6555f
async def test_consumes_empty_tuple_drops_everything(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """consumes=() — explicit empty allowlist drops every caller param."""
    step = FlowStep(ref_id="test.noop", kind=StepKind.ACTION, consumes=())
    received = await _invoke(
        monkeypatch, step, {"source_file": "src/x.py", "extra": 42}
    )
    assert received == {"write": False}
