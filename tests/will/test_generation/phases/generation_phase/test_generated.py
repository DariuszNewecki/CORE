from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from will.test_generation.phases.generation_phase import GenerationPhase


@pytest.mark.asyncio
# ID: 31368196-aa8c-45d6-b12b-dd5aa743d4fd
async def test_GenerationPhase():
    test_strategist = MagicMock()
    test_strategist.execute = AsyncMock()

    failure_evaluator = MagicMock()
    failure_evaluator.execute = AsyncMock()

    test_executor = MagicMock()
    test_executor.execute = AsyncMock(
        return_value={
            "validated": True,
            "sandbox_passed": True,
            "sandbox_ran": True,
        }
    )

    phase = GenerationPhase(
        test_strategist=test_strategist,
        failure_evaluator=failure_evaluator,
        test_executor=test_executor,
    )

    symbols = [
        {"name": "alpha"},
        {"name": "beta"},
    ]

    initial_strategy = MagicMock()
    context_service = MagicMock()

    result = await phase.execute(
        file_path="pkg/mod.py",
        symbols=symbols,
        initial_strategy=initial_strategy,
        context_service=context_service,
        write=False,
        max_failures_per_pattern=3,
        file_type="module",
        complexity="low",
        has_db_harness=False,
    )

    assert result["total_symbols"] == 2
    assert result["tests_generated"] == 2
    assert result["sandbox_passed"] == 2
    assert result["tests_failed"] == 0
    assert result["tests_skipped"] == 0
    assert result["strategy_switches"] == 0
    assert result["success_rate"] == 1.0
    assert len(result["generated_tests"]) == 2

    assert test_executor.execute.await_count == 2
    assert failure_evaluator.execute.await_count == 0
    assert test_strategist.execute.await_count == 0

    first_call_kwargs = test_executor.execute.await_args_list[0].kwargs
    assert first_call_kwargs["file_path"] == "pkg/mod.py"
    assert first_call_kwargs["symbol"] == {"name": "alpha"}
    assert first_call_kwargs["strategy"] is initial_strategy
    assert first_call_kwargs["context_service"] is context_service
    assert first_call_kwargs["write"] is False
