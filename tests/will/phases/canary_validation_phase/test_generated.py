from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


# ID: eaec3bc8-f7be-4d1b-9e15-9c522745853d
def test_CanaryValidationPhase_execute():
    with (
        patch("will.phases.canary_validation_phase.DecisionTracer"),
        patch("will.phases.canary_validation_phase.TestDiscoveryService"),
        patch("will.phases.canary_validation_phase.PytestRunner"),
        patch("will.phases.canary_validation_phase.CanaryResultBuilder"),
    ):
        from will.phases.canary_validation_phase import CanaryValidationPhase

        core_context = MagicMock()
        core_context.path_resolver = MagicMock()

        executor = MagicMock()
        import_result = MagicMock()
        import_result.ok = True
        import_result.data = {}
        executor.execute = AsyncMock(return_value=import_result)
        core_context.action_executor = executor

        phase = CanaryValidationPhase(core_context)

        phase._extract_affected_files = MagicMock(return_value=["src/foo.py"])
        phase._trace_test_execution = MagicMock()

        test_paths = ["tests/test_foo.py"]
        phase.test_discovery.find_related_tests.return_value = test_paths

        test_result = {"exit_code": 0}
        phase.pytest_runner.run_tests = AsyncMock(return_value=test_result)

        success_result = MagicMock(name="success_result")
        phase.result_builder.build_success_result.return_value = success_result

        results = MagicMock()
        results.get = MagicMock(
            side_effect=lambda k, d=None: {
                "code_generation": {"detailed_plan": {"files": ["src/foo.py"]}}
            }.get(k, d)
        )
        context = MagicMock()
        context.results = results

        result = asyncio.run(phase.execute(context))

        executor.execute.assert_awaited_once_with(
            action_id="check.imports", write=False
        )
        phase.test_discovery.find_related_tests.assert_called_once_with(["src/foo.py"])
        phase.pytest_runner.run_tests.assert_awaited_once_with(test_paths)
        phase._trace_test_execution.assert_called_once_with(test_paths, test_result)
        phase.result_builder.build_success_result.assert_called_once()
        assert result is success_result
