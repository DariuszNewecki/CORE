# tests/will/agents/test_iterative_coder_agent.py
"""Tests for IterativeCoderAgent (ADR-135 D2)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from will.agents.acceptance.conditions import (
    AcceptanceResult,
)
from will.agents.iterative_coder_agent import IterativeCoderAgent


def _make_task():
    task = MagicMock()
    task.step = "test_step"
    task.task_type = "test_generation"
    return task


def _make_coder_agent(return_value: str = "def test_foo(): assert True"):
    agent = MagicMock()
    agent.generate_or_repair = AsyncMock(return_value=return_value)
    return agent


def _make_accept_condition(accepted: bool, violations=None):
    cond = MagicMock()
    cond.evaluate = AsyncMock(
        return_value=AcceptanceResult(
            accepted=accepted,
            violation_summary="no assertions" if not accepted else "",
            violations=violations or (["no assertions"] if not accepted else []),
        )
    )
    return cond


@pytest.mark.asyncio
async def test_accepted_on_first_attempt():
    agent = _make_coder_agent("good code")
    cond = _make_accept_condition(accepted=True)
    iterative = IterativeCoderAgent(coder_agent=agent)

    with patch(
        "will.agents.iterative_coder_agent.load_generation_budget"
    ) as mock_budget:
        from shared.infrastructure.intent.generation_budget import TaskBudget
        mock_budget.return_value.for_task_type.return_value = TaskBudget(5, 600)
        result = await iterative.generate_until_accepted(
            task=_make_task(), goal="generate test", acceptance=cond
        )

    assert result.accepted
    assert result.iterations_used == 1
    assert result.final_violations == []
    agent.generate_or_repair.assert_called_once_with(
        task=_make_task(), goal="generate test", pain_signal=None, previous_code=None
    )


@pytest.mark.asyncio
async def test_retries_on_rejection_and_accepts_second():
    agent = _make_coder_agent("fixed code")
    cond = MagicMock()
    cond.evaluate = AsyncMock(
        side_effect=[
            AcceptanceResult(accepted=False, violation_summary="no assert", violations=["no assert"]),
            AcceptanceResult(accepted=True, violation_summary="", violations=[]),
        ]
    )
    iterative = IterativeCoderAgent(coder_agent=agent)

    with patch(
        "will.agents.iterative_coder_agent.load_generation_budget"
    ) as mock_budget:
        from shared.infrastructure.intent.generation_budget import TaskBudget
        mock_budget.return_value.for_task_type.return_value = TaskBudget(5, 600)
        result = await iterative.generate_until_accepted(
            task=_make_task(), goal="generate test", acceptance=cond
        )

    assert result.accepted
    assert result.iterations_used == 2
    assert agent.generate_or_repair.call_count == 2
    # Second call gets pain_signal from first rejection
    second_call_kwargs = agent.generate_or_repair.call_args_list[1].kwargs
    assert second_call_kwargs["pain_signal"] == "no assert"


@pytest.mark.asyncio
async def test_cap_exhausted_returns_not_accepted():
    agent = _make_coder_agent("bad code")
    cond = _make_accept_condition(accepted=False)
    iterative = IterativeCoderAgent(coder_agent=agent)

    with patch(
        "will.agents.iterative_coder_agent.load_generation_budget"
    ) as mock_budget:
        from shared.infrastructure.intent.generation_budget import TaskBudget
        mock_budget.return_value.for_task_type.return_value = TaskBudget(3, 600)
        result = await iterative.generate_until_accepted(
            task=_make_task(), goal="generate test", acceptance=cond
        )

    assert not result.accepted
    assert result.iterations_used == 3
    assert agent.generate_or_repair.call_count == 3


@pytest.mark.asyncio
async def test_caller_cap_clamped_to_governed():
    agent = _make_coder_agent("bad code")
    cond = _make_accept_condition(accepted=False)
    iterative = IterativeCoderAgent(coder_agent=agent)

    with patch(
        "will.agents.iterative_coder_agent.load_generation_budget"
    ) as mock_budget:
        from shared.infrastructure.intent.generation_budget import TaskBudget
        mock_budget.return_value.for_task_type.return_value = TaskBudget(2, 600)
        result = await iterative.generate_until_accepted(
            task=_make_task(),
            goal="generate test",
            acceptance=cond,
            caller_cap=100,  # exceeds governed cap of 2
        )

    assert not result.accepted
    assert result.iterations_used == 2  # governed cap wins


def test_generation_mode_property():
    from shared.models.generation_mode import GenerationMode

    iterative = IterativeCoderAgent(coder_agent=MagicMock())
    assert iterative.generation_mode == GenerationMode.ITERATIVE
