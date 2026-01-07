# tests/features/self_healing/test_batch_remediation_service.py
import pytest


pytestmark = pytest.mark.legacy

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from features.self_healing.batch_remediation_service import BatchRemediationService


@pytest.mark.asyncio
class TestBatchRemediationService:
    # The order of decorators matters. The bottom one runs first.
    @patch("pathlib.Path.exists")  # Add this patch to bypass the filesystem check
    @patch(
        "features.self_healing.batch_remediation_service.EnhancedSingleFileRemediationService"
    )
    @patch("features.self_healing.complexity_filter.ComplexityFilter")
    @patch("features.self_healing.batch_remediation_service.CoverageAnalyzer")
    async def test_process_batch_selects_and_filters_correctly(
        self,
        mock_coverage_analyzer_cls: MagicMock,
        mock_complexity_filter_cls: MagicMock,
        mock_remediation_service_cls: MagicMock,
        mock_path_exists: MagicMock,  # The new mock argument
    ):
        """
        Verify the core logic of selecting, filtering, and processing candidates.
        """
        # --- Arrange ---

        # 1. Force path.exists() to always return True for this test
        mock_path_exists.return_value = True

        # 2. Configure CoverageAnalyzer Mock
        mock_analyzer_instance = mock_coverage_analyzer_cls.return_value
        mock_analyzer_instance.get_module_coverage.return_value = {
            "src/utils/too_low.py": 10.5,
            "src/services/needs_work.py": 50.0,
            "src/core/good_enough.py": 80.0,
            "src/utils/also_too_low.py": 25.0,
            "src/features/complex_but_low.py": 30.0,
        }

        # 3. Configure ComplexityFilter Mock
        mock_filter_instance = mock_complexity_filter_cls.return_value

        def should_attempt_side_effect(file_path: Path):
            if "complex" in file_path.name:
                return {"should_attempt": False, "reason": "Too complex"}
            return {"should_attempt": True, "reason": "Within threshold"}

        mock_filter_instance.should_attempt.side_effect = should_attempt_side_effect

        # 4. Configure Remediation Service Mock
        mock_remediation_instance = mock_remediation_service_cls.return_value
        mock_remediation_instance.remediate = AsyncMock(
            return_value={"status": "success"}
        )

        # 5. Instantiate the service under test
        service = BatchRemediationService(
            cognitive_service=MagicMock(),
            auditor_context=MagicMock(),
            max_complexity="MODERATE",
        )

        # --- Act ---
        result = await service.process_batch(count=2)

        # --- Assert ---
        assert result["status"] == "completed"
        assert result["processed"] == 2

        mock_analyzer_instance.get_module_coverage.assert_called_once()
        # It will be called 4 times for the 4 files with < 75% coverage
        assert mock_filter_instance.should_attempt.call_count == 4

        call_args_list = mock_remediation_service_cls.call_args_list
        processed_paths = [call.args[2] for call in call_args_list]

        assert "too_low.py" in str(processed_paths[0])
        assert "also_too_low.py" in str(processed_paths[1])

    @patch("features.self_healing.batch_remediation_service.CoverageAnalyzer")
    async def test_process_batch_handles_no_candidates(
        self,
        mock_coverage_analyzer_cls: MagicMock,
    ):
        # Arrange
        mock_analyzer_instance = mock_coverage_analyzer_cls.return_value
        mock_analyzer_instance.get_module_coverage.return_value = {}

        service = BatchRemediationService(
            cognitive_service=MagicMock(),
            auditor_context=MagicMock(),
        )

        # Act
        result = await service.process_batch(count=5)

        # Assert
        assert result["status"] == "no_candidates"
        assert result["processed"] == 0
