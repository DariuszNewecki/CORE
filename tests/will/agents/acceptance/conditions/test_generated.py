from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from will.agents.acceptance.conditions import CompositeAcceptanceCondition


# ID: 64769bd5-76d4-43ad-bb68-cc6d7c9fbfd2
async def test_CompositeAcceptanceCondition_evaluate():
    accepted_result = MagicMock()
    accepted_result.accepted = True
    accepted_result.violation_summary = ""

    condition_a = MagicMock()
    condition_a.evaluate = AsyncMock(return_value=accepted_result)
    condition_b = MagicMock()
    condition_b.evaluate = AsyncMock(return_value=accepted_result)

    composite = CompositeAcceptanceCondition([condition_a, condition_b])

    result = await composite.evaluate("some code")

    assert result.accepted is True
    assert result.violation_summary == ""
    condition_a.evaluate.assert_awaited_once_with("some code")
    condition_b.evaluate.assert_awaited_once_with("some code")


import asyncio


# ID: 18835eea-3ae1-404d-91fa-6a8e21f9f756
def test_CompositeAcceptanceCondition():
    passing = MagicMock()
    passing.evaluate = AsyncMock(
        return_value=MagicMock(accepted=True, violation_summary="")
    )
    failing = MagicMock()
    failing.evaluate = AsyncMock(
        return_value=MagicMock(accepted=False, violation_summary="boom")
    )

    # ID: 61206fcf-411d-421f-948d-8fcbf16bb199
    async def run():
        composite = CompositeAcceptanceCondition([passing, failing])
        result = await composite.evaluate("ok()[code]")
        return composite, result

    composite, result = asyncio.run(run())

    assert result.accepted is False
    assert result.violation_summary == "boom"
    passing.evaluate.assert_awaited_once_with("ok()[code]")
    failing.evaluate.assert_awaited_once_with("ok()[code]")
    assert composite._conditions == [passing, failing]


from unittest.mock import patch

from will.agents.acceptance.conditions import PytestAcceptanceCondition


# ID: bd22d339-bf22-45c1-83c1-853a4ae3a444
async def test_PytestAcceptanceCondition_evaluate() -> None:
    mock_executor = MagicMock()
    mock_executor.__class__ = type(
        "FakeExecutor",
        (),
        {},
    )

    mock_result = MagicMock()
    mock_result.ok = True
    mock_executor.execute = AsyncMock(return_value=mock_result)

    condition = PytestAcceptanceCondition(
        executor=mock_executor,
        source_file="src/pkg/module.py",
        target_path="tests/test_module.py",
        base_content="",
    )

    code = "def test_example():\n    assert True\n"

    with patch(
        "will.agents.acceptance.conditions.isinstance",
        return_value=True,
    ):
        result = await condition.evaluate(code)

    assert result.accepted is True
    mock_executor.execute.assert_awaited_once()
    call_args = mock_executor.execute.await_args
    assert call_args.args[0] == "test.candidate_validate"
    assert call_args.kwargs["write"] is False
    assert call_args.kwargs["source_file"] == "src/pkg/module.py"
    assert call_args.kwargs["target_path"] == "tests/test_module.py"
    assert "def test_example" in call_args.kwargs["candidate_content"]


# ID: 829285fc-a339-4702-9416-7ee8dc56c0ac
async def test_PytestAcceptanceCondition() -> None:
    from shared.protocols.executor import ActionExecutorProtocol

    executor = MagicMock(spec=ActionExecutorProtocol)
    executor.execute = AsyncMock(return_value=MagicMock(ok=True, data={}))

    condition = PytestAcceptanceCondition(
        executor=executor,
        source_file="src/pkg/mod.py",
        target_path="tests/test_mod.py",
        base_content="def existing():\n    return 1\n",
    )

    with patch(
        "will.agents.acceptance.conditions.strip_leading_future_imports",
        return_value="def test_mod():\n    assert True\n",
    ):
        result = await condition.evaluate(
            "from __future__ import annotations\n\n\ndef test_mod():\n    assert True\n"
        )

    assert result.accepted is True
    assert result.violation_summary == ""
    executor.execute.assert_awaited_once()
    call_args, call_kwargs = executor.execute.await_args
    assert call_args[0] == "test.candidate_validate"
    assert call_kwargs["write"] is False
    assert call_kwargs["source_file"] == "src/pkg/mod.py"
    assert call_kwargs["target_path"] == "tests/test_mod.py"
    assert "def test_mod():" in call_kwargs["candidate_content"]
    assert "def existing():" in call_kwargs["candidate_content"]


from pathlib import Path

from will.agents.acceptance.conditions import IntentGuardAcceptanceCondition


# ID: ecda5bc1-96a0-446c-8019-0080306d1b9f
async def test_IntentGuardAcceptanceCondition_evaluate():
    condition = IntentGuardAcceptanceCondition(
        repo_root=Path("/tmp/repo"),
        target_path="tests/test_example.py",
        component_type="test",
    )

    mock_validation = MagicMock()
    mock_validation.is_valid = True
    mock_validation.violations = []

    mock_guard = MagicMock()
    mock_guard.validate_generated_code = MagicMock(return_value=mock_validation)

    with patch(
        "body.governance.intent_guard.get_intent_guard",
        return_value=mock_guard,
    ) as mock_get_guard:
        result = await condition.evaluate("def test_foo():\n    assert True\n")

    mock_get_guard.assert_called_once_with(repo_path=Path("/tmp/repo"))
    mock_guard.validate_generated_code.assert_called_once_with(
        code="def test_foo():\n    assert True\n",
        pattern_id="test_file",
        component_type="test",
        target_path="tests/test_example.py",
    )
    assert result.accepted is True
    assert result.violation_summary == ""





# ID: 4cea1866-d702-4903-a0e9-3ec02f9992c7
def test_IntentGuardAcceptanceCondition():
    repo_root = Path("/tmp/repo")
    condition = IntentGuardAcceptanceCondition(
        repo_root=repo_root, target_path="tests/test_foo.py", component_type="test"
    )

    mock_validation = MagicMock()
    mock_validation.is_valid = True
    mock_validation.violations = []

    mock_guard = MagicMock()
    mock_guard.validate_generated_code = MagicMock(return_value=mock_validation)

    with patch(
        "body.governance.intent_guard.get_intent_guard", return_value=mock_guard
    ):
        result = asyncio.run(condition.evaluate("def test_foo():\n    assert True\n"))

    assert result.accepted is True
    assert result.violation_summary == ""
    mock_guard.validate_generated_code.assert_called_once_with(
        code="def test_foo():\n    assert True\n",
        pattern_id="test_file",
        component_type="test",
        target_path="tests/test_foo.py",
    )
