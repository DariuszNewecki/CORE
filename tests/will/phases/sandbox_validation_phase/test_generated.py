from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from will.phases.sandbox_validation_phase import SandboxValidationPhase


# ID: e63d4dc2-5774-437b-8e88-f71aab6ed726
async def test_SandboxValidationPhase_execute():
    mock_context = MagicMock()
    mock_context.file_service = MagicMock()
    mock_context.git_service.repo_path = "/tmp/repo"

    with patch(
        "will.phases.sandbox_validation_phase.PytestSandboxRunner"
    ) as mock_runner_cls:
        mock_sandbox = MagicMock()
        sandbox_result = MagicMock()
        sandbox_result.passed = True
        sandbox_result.error = None
        sandbox_result.passed_tests = 1
        sandbox_result.failed_tests = 0
        mock_sandbox.run = AsyncMock(return_value=sandbox_result)
        mock_runner_cls.return_value = mock_sandbox

        phase = SandboxValidationPhase(mock_context)
        phase.sandbox = mock_sandbox

        ctx = MagicMock()
        ctx.results = {
            "test_generation": {
                "generated_tests": [{"code": "def test_x(): pass", "symbol_name": "x"}]
            }
        }

        result = await phase.execute(ctx)

    assert result.ok is True
    assert result.data["total_tests"] == 1
    assert result.data["passed"] == 1
    assert result.data["failed"] == 0
    assert len(result.data["results"]) == 1
    assert result.data["results"][0]["symbol_name"] == "x"
    assert result.data["results"][0]["passed"] is True
    mock_sandbox.run.assert_awaited_once()
