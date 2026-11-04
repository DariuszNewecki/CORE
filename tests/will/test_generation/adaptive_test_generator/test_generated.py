from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch


# ID: e4b0a988-f5eb-4fcc-b549-2e16ee8af84b
async def test_AdaptiveTestGenerator_generate_tests_for_file():
    from will.test_generation.adaptive_test_generator import AdaptiveTestGenerator

    context = MagicMock()
    context.git_service.repo_path = "/tmp/repo"

    generator = AdaptiveTestGenerator.__new__(AdaptiveTestGenerator)
    generator.context = context
    generator.session_dir = "/tmp/session"
    generator.artifacts = MagicMock()
    generator.parse_phase = MagicMock()
    generator.parse_phase.execute = AsyncMock(return_value=True)
    generator.load_phase = MagicMock()
    generator.load_phase.execute = AsyncMock(return_value=MagicMock())
    generator.generation_phase = MagicMock()
    generator.generation_phase.execute = AsyncMock(
        return_value={
            "generated_tests": ["test_one"],
            "strategy_switches": 1,
            "patterns_learned": 2,
        }
    )
    generator._empty_fail = MagicMock()

    mock_analysis = MagicMock()
    mock_analysis.data = {"file_type": "service", "complexity": "low"}
    mock_harness = MagicMock()
    mock_harness.has_db_harness = False
    mock_symbols_result = MagicMock()
    mock_symbols_result.data = {"symbols": []}
    mock_final_result = MagicMock()

    with (
        patch(
            "will.test_generation.adaptive_test_generator.FileAnalyzer"
        ) as mock_file_analyzer,
        patch(
            "will.test_generation.adaptive_test_generator.HarnessDetector"
        ) as mock_harness_detector,
        patch(
            "will.test_generation.adaptive_test_generator.SymbolExtractor"
        ) as mock_symbol_extractor,
        patch(
            "will.test_generation.adaptive_test_generator.TestStrategist"
        ) as mock_test_strategist,
        patch(
            "will.test_generation.adaptive_test_generator.TestResultAggregator"
        ) as mock_aggregator_cls,
    ):
        mock_file_analyzer.return_value.execute = AsyncMock(return_value=mock_analysis)
        mock_harness_detector.return_value.detect.return_value = mock_harness
        mock_symbol_extractor.return_value.execute = AsyncMock(
            return_value=mock_symbols_result
        )
        mock_test_strategist.return_value.execute = AsyncMock(return_value="strategy_a")

        mock_aggregator = MagicMock()
        mock_aggregator.build_final_result.return_value = mock_final_result
        mock_aggregator.format_summary_json.return_value = {"summary": "ok"}
        mock_aggregator_cls.return_value = mock_aggregator

        result = await generator.generate_tests_for_file("src/foo.py", write=False)

    assert result is mock_final_result
    generator.parse_phase.execute.assert_awaited_once_with("src/foo.py")
    generator.load_phase.execute.assert_awaited_once()
    generator.generation_phase.execute.assert_awaited_once()
    generator.artifacts.write_summary.assert_called_once_with(
        "/tmp/session", {"summary": "ok"}
    )
    generator._empty_fail.assert_not_called()


# ID: 85b29739-7e6b-499b-9d6f-19b777303f35
def test_AdaptiveTestGenerator():
    from unittest.mock import MagicMock, patch

    from will.test_generation.adaptive_test_generator import AdaptiveTestGenerator

    mock_context = MagicMock()
    mock_context.git_service.repo_path = "/tmp/repo"

    mock_session = MagicMock()
    mock_session.session_dir = "/tmp/repo/.session"

    with (
        patch(
            "will.test_generation.adaptive_test_generator.FileService"
        ) as mock_file_service,
        patch(
            "will.test_generation.adaptive_test_generator.TestGenArtifactStore"
        ) as mock_artifact_store_cls,
        patch(
            "will.test_generation.adaptive_test_generator.ParsePhase"
        ) as mock_parse_phase_cls,
        patch(
            "will.test_generation.adaptive_test_generator.LoadPhase"
        ) as mock_load_phase_cls,
        patch("will.test_generation.adaptive_test_generator.TestExecutor"),
        patch("will.test_generation.adaptive_test_generator.PythonOutputNormalizer"),
        patch("will.test_generation.adaptive_test_generator.GeneratedTestValidator"),
        patch("will.test_generation.adaptive_test_generator.PytestSandboxRunner"),
        patch("will.test_generation.adaptive_test_generator.TestPersistenceService"),
        patch(
            "will.test_generation.adaptive_test_generator.ConstitutionalTestPromptBuilder"
        ),
        patch("will.test_generation.adaptive_test_generator.GenerationPhase"),
        patch("will.test_generation.adaptive_test_generator.TestStrategist"),
        patch("will.test_generation.adaptive_test_generator.FailureEvaluator"),
    ):
        mock_artifact_store_cls.return_value.start_session.return_value = mock_session

        generator = AdaptiveTestGenerator(context=mock_context)

        assert generator.context is mock_context
        assert generator.session_dir == "/tmp/repo/.session"
        mock_artifact_store_cls.return_value.start_session.assert_called_once()
        mock_parse_phase_cls.assert_called_once_with(mock_context)
        mock_load_phase_cls.assert_called_once_with(mock_context)
