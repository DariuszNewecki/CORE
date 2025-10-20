from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import jsonschema
import pytest
import yaml
from core.crate_processing_service import Crate, CrateProcessingService, process_crates
from shared.models import AuditFinding


class TestCrate:
    def test_crate_initialization(self):
        """Test that Crate dataclass initializes correctly."""
        # Arrange
        test_path = Path("/test/path")
        test_manifest = {"intent": "test", "type": "STANDARD"}

        # Act
        crate = Crate(path=test_path, manifest=test_manifest)

        # Assert
        assert crate.path == test_path
        assert crate.manifest == test_manifest


class TestCrateProcessingService:
    @pytest.fixture
    def service(self):
        """Create a CrateProcessingService instance with mocked dependencies."""
        with (
            patch("core.crate_processing_service.settings") as mock_settings,
            patch("core.crate_processing_service.action_logger"),
            patch("core.crate_processing_service.console"),
        ):
            mock_settings.REPO_PATH = Path("/test/repo")
            mock_settings.load.side_effect = lambda key: {
                "charter.policies.governance.intent_crate_policy": {"policy": "test"},
                "charter.schemas.constitutional.intent_crate_schema": {
                    "schema": "test"
                },
            }[key]

            return CrateProcessingService()

    def test_init_creates_directories(self, service):
        """Test that service initialization creates required directories."""
        # Arrange
        mock_path = Mock()
        mock_path.mkdir = Mock()

        # Act - service is already initialized in fixture

        # Assert
        expected_paths = [
            service.inbox_path,
            service.processing_path,
            service.accepted_path,
            service.rejected_path,
        ]

        for path in expected_paths:
            path.mkdir.assert_called_once_with(parents=True, exist_ok=True)

    @patch("core.crate_processing_service.settings._load_file_content")
    @patch("core.crate_processing_service.jsonschema.validate")
    def test_scan_and_validate_inbox_valid_crate(
        self, mock_validate, mock_load_file, service
    ):
        """Test scanning inbox with valid crate."""
        # Arrange
        crate_id = "test-crate-123"
        test_manifest = {"intent": "test intent", "type": "STANDARD"}

        mock_crate_dir = Mock()
        mock_crate_dir.is_dir.return_value = True
        mock_crate_dir.name = crate_id

        mock_manifest_path = Mock()
        mock_manifest_path.exists.return_value = True

        mock_crate_dir.__truediv__.return_value = mock_manifest_path
        service.inbox_path.exists.return_value = True
        service.inbox_path.iterdir.return_value = [mock_crate_dir]
        mock_load_file.return_value = test_manifest

        # Act
        result = service._scan_and_validate_inbox()

        # Assert
        assert len(result) == 1
        assert result[0].path == mock_crate_dir
        assert result[0].manifest == test_manifest
        mock_validate.assert_called_once_with(
            instance=test_manifest, schema=service.crate_schema
        )

    @patch("core.crate_processing_service.settings._load_file_content")
    def test_scan_and_validate_inbox_missing_manifest(self, mock_load_file, service):
        """Test scanning inbox with crate missing manifest."""
        # Arrange
        crate_id = "test-crate-123"
        mock_crate_dir = Mock()
        mock_crate_dir.is_dir.return_value = True
        mock_crate_dir.name = crate_id

        mock_manifest_path = Mock()
        mock_manifest_path.exists.return_value = False

        mock_crate_dir.__truediv__.return_value = mock_manifest_path
        service.inbox_path.exists.return_value = True
        service.inbox_path.iterdir.return_value = [mock_crate_dir]

        # Act
        result = service._scan_and_validate_inbox()

        # Assert
        assert len(result) == 0

    @patch("core.crate_processing_service.settings._load_file_content")
    @patch("core.crate_processing_service.jsonschema.validate")
    def test_scan_and_validate_inbox_validation_error(
        self, mock_validate, mock_load_file, service
    ):
        """Test scanning inbox with crate that fails validation."""
        # Arrange
        crate_id = "test-crate-123"
        test_manifest = {"intent": "test intent"}

        mock_crate_dir = Mock()
        mock_crate_dir.is_dir.return_value = True
        mock_crate_dir.name = crate_id

        mock_manifest_path = Mock()
        mock_manifest_path.exists.return_value = True

        mock_crate_dir.__truediv__.return_value = mock_manifest_path
        service.inbox_path.exists.return_value = True
        service.inbox_path.iterdir.return_value = [mock_crate_dir]
        mock_load_file.return_value = test_manifest

        mock_validate.side_effect = jsonschema.ValidationError("Invalid schema")

        with patch.object(service, "_move_crate_to_rejected") as mock_reject:
            # Act
            result = service._scan_and_validate_inbox()

            # Assert
            assert len(result) == 0
            mock_reject.assert_called_once()

    def test_copy_tree_with_ignore_patterns(self, service):
        """Test the _copy_tree method with ignore patterns."""
        # Arrange
        src = Mock()
        dst = Mock()
        ignore_patterns = [".git", "__pycache__"]

        file1 = Mock()
        file1.name = "test.py"
        file1.is_dir.return_value = False

        file2 = Mock()
        file2.name = ".git"
        file2.is_dir.return_value = False

        dir1 = Mock()
        dir1.name = "src"
        dir1.is_dir.return_value = True

        src.iterdir.return_value = [file1, file2, dir1]

        # Act
        service._copy_tree(src, dst, ignore_patterns)

        # Assert
        # Should only copy file1 and dir1, not file2 (.git)
        file1.read_bytes.assert_called_once()

    def test_copy_file_creates_parents(self, service):
        """Test that _copy_file creates parent directories."""
        # Arrange
        src = Mock()
        dst = Mock()

        dst.parent.mkdir = Mock()
        src.read_bytes.return_value = b"test content"

        # Act
        service._copy_file(src, dst)

        # Assert
        dst.parent.mkdir.assert_called_once_with(parents=True, exist_ok=True)
        dst.write_bytes.assert_called_once_with(b"test content")

    @pytest.mark.asyncio
    @patch("core.crate_processing_service.KnowledgeGraphBuilder")
    @patch("core.crate_processing_service.ConstitutionalAuditor")
    async def test_run_canary_validation_success(
        self, mock_auditor_class, mock_builder_class, service
    ):
        """Test canary validation with successful audit."""
        # Arrange
        crate = Crate(
            path=Path("/test/crate"),
            manifest={"payload_files": ["file1.py"], "type": "STANDARD"},
        )

        mock_auditor = AsyncMock()
        mock_auditor.run_full_audit_async.return_value = [
            {"severity": "info", "message": "Test finding"}
        ]
        mock_auditor_class.return_value = mock_auditor

        mock_builder = Mock()
        mock_builder.build = Mock()
        mock_builder_class.return_value = mock_builder

        with (
            patch.object(service, "_copy_tree") as mock_copy_tree,
            patch.object(service, "_copy_file") as mock_copy_file,
            patch(
                "core.crate_processing_service.tempfile.TemporaryDirectory"
            ) as mock_temp,
        ):
            mock_temp.return_value.__enter__.return_value = "/tmp/test"

            # Act
            result_passed, result_findings = await service._run_canary_validation(crate)

            # Assert
            assert result_passed is True
            assert result_findings == []
            mock_copy_tree.assert_called_once()
            mock_builder.build.assert_called_once()
            mock_auditor.run_full_audit_async.assert_called_once()

    @pytest.mark.asyncio
    @patch("core.crate_processing_service.KnowledgeGraphBuilder")
    @patch("core.crate_processing_service.ConstitutionalAuditor")
    async def test_run_canary_validation_failure(
        self, mock_auditor_class, mock_builder_class, service
    ):
        """Test canary validation with failed audit."""
        # Arrange
        crate = Crate(
            path=Path("/test/crate"),
            manifest={"payload_files": ["file1.py"], "type": "STANDARD"},
        )

        test_findings = [
            {"severity": "error", "message": "Critical violation"},
            {"severity": "warning", "message": "Minor issue"},
        ]

        mock_auditor = AsyncMock()
        mock_auditor.run_full_audit_async.return_value = test_findings
        mock_auditor_class.return_value = mock_auditor

        mock_builder = Mock()
        mock_builder.build = Mock()
        mock_builder_class.return_value = mock_builder

        with (
            patch.object(service, "_copy_tree") as mock_copy_tree,
            patch.object(service, "_copy_file") as mock_copy_file,
            patch(
                "core.crate_processing_service.tempfile.TemporaryDirectory"
            ) as mock_temp,
        ):
            mock_temp.return_value.__enter__.return_value = "/tmp/test"

            # Act
            result_passed, result_findings = await service._run_canary_validation(crate)

            # Assert
            assert result_passed is False
            assert len(result_findings) == 2
            assert all(isinstance(f, AuditFinding) for f in result_findings)

    def test_apply_accepted_crate_standard_type(self, service):
        """Test applying accepted crate with STANDARD type."""
        # Arrange
        crate = Crate(
            path=Path("/test/crate"),
            manifest={
                "payload_files": ["src/file1.py", "config/file2.yaml"],
                "type": "STANDARD",
            },
        )

        with patch.object(service, "_copy_file") as mock_copy_file:
            # Act
            service._apply_accepted_crate(crate)

            # Assert
            assert mock_copy_file.call_count == 2
            # Verify correct target paths for STANDARD type
            calls = mock_copy_file.call_args_list
            assert any(str(call[0][1]).endswith("src/file1.py") for call in calls)
            assert any(str(call[0][1]).endswith("config/file2.yaml") for call in calls)

    def test_apply_accepted_crate_constitutional_amendment(self, service):
        """Test applying accepted crate with CONSTITUTIONAL_AMENDMENT type."""
        # Arrange
        crate = Crate(
            path=Path("/test/crate"),
            manifest={
                "payload_files": ["policy1.yaml", "policy2.yaml"],
                "type": "CONSTITUTIONAL_AMENDMENT",
            },
        )

        with patch.object(service, "_copy_file") as mock_copy_file:
            # Act
            service._apply_accepted_crate(crate)

            # Assert
            assert mock_copy_file.call_count == 2
            # Verify correct target paths for CONSTITUTIONAL_AMENDMENT type
            calls = mock_copy_file.call_args_list
            assert any(
                ".intent/charter/policies/governance/policy1.yaml" in str(call[0][1])
                for call in calls
            )
            assert any(
                ".intent/charter/policies/governance/policy2.yaml" in str(call[0][1])
                for call in calls
            )

    def test_write_result_manifest_with_string_details(self, service):
        """Test writing result manifest with string details."""
        # Arrange
        crate_path = Path("/test/crate")
        status = "accepted"
        details = "Changes applied successfully"

        with (
            patch.object(crate_path, "write_text") as mock_write,
            patch("core.crate_processing_service.datetime") as mock_datetime,
        ):
            mock_datetime.now.return_value = datetime(2023, 1, 1, tzinfo=UTC)
            mock_datetime.UTC = UTC

            # Act
            service._write_result_manifest(crate_path, status, details)

            # Assert
            mock_write.assert_called_once()
            call_args = mock_write.call_args[0][0]
            result_data = yaml.safe_load(call_args)
            assert result_data["status"] == status
            assert result_data["justification"] == details

    def test_write_result_manifest_with_list_details(self, service):
        """Test writing result manifest with list of findings."""
        # Arrange
        crate_path = Path("/test/crate")
        status = "rejected"
        findings = [
            AuditFinding(severity="error", message="Test violation 1"),
            AuditFinding(severity="warning", message="Test violation 2"),
        ]

        with (
            patch.object(crate_path, "write_text") as mock_write,
            patch("core.crate_processing_service.datetime") as mock_datetime,
        ):
            mock_datetime.now.return_value = datetime(2023, 1, 1, tzinfo=UTC)
            mock_datetime.UTC = UTC

            # Act
            service._write_result_manifest(crate_path, status, findings)

            # Assert
            mock_write.assert_called_once()
            call_args = mock_write.call_args[0][0]
            result_data = yaml.safe_load(call_args)
            assert result_data["status"] == status
            assert len(result_data["violations"]) == 2

    @pytest.mark.asyncio
    @patch.object(CrateProcessingService, "_scan_and_validate_inbox")
    async def test_process_pending_crates_async_no_crates(self, mock_scan, service):
        """Test processing when no valid crates are found."""
        # Arrange
        mock_scan.return_value = []

        # Act
        await service.process_pending_crates_async()

        # Assert
        mock_scan.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(CrateProcessingService, "_run_canary_validation")
    @patch.object(CrateProcessingService, "_scan_and_validate_inbox")
    async def test_process_pending_crates_async_successful_processing(
        self, mock_scan, mock_canary, service
    ):
        """Test successful processing of a valid crate."""
        # Arrange
        crate = Crate(
            path=Path("/test/inbox/test-crate"),
            manifest={"payload_files": ["file1.py"], "type": "STANDARD"},
        )
        mock_scan.return_value = [crate]
        mock_canary.return_value = (True, [])  # Canary passes

        with (
            patch.object(service.processing_path, "__truediv__") as mock_div,
            patch.object(crate.path, "rename") as mock_rename,
            patch.object(service, "_apply_accepted_crate") as mock_apply,
            patch.object(service.accepted_path, "__truediv__") as mock_accept_div,
        ):
            mock_div.return_value = Path("/test/processing/test-crate")
            mock_accept_div.return_value = Path("/test/accepted/test-crate")

            # Act
            await service.process_pending_crates_async()

            # Assert
            mock_scan.assert_called_once()
            mock_canary.assert_called_once_with(crate)
            mock_apply.assert_called_once_with(crate)
            mock_rename.assert_called()

    @pytest.mark.asyncio
    @patch.object(CrateProcessingService, "_run_canary_validation")
    @patch.object(CrateProcessingService, "_scan_and_validate_inbox")
    async def test_process_pending_crates_async_failed_processing(
        self, mock_scan, mock_canary, service
    ):
        """Test processing when crate fails canary validation."""
        # Arrange
        crate = Crate(
            path=Path("/test/inbox/test-crate"),
            manifest={"payload_files": ["file1.py"], "type": "STANDARD"},
        )
        test_findings = [
            AuditFinding(severity="error", message="Constitutional violation")
        ]

        mock_scan.return_value = [crate]
        mock_canary.return_value = (False, test_findings)  # Canary fails

        with (
            patch.object(service.processing_path, "__truediv__") as mock_div,
            patch.object(crate.path, "rename") as mock_rename,
            patch.object(service, "_move_crate_to_rejected") as mock_reject,
        ):
            mock_div.return_value = Path("/test/processing/test-crate")

            # Act
            await service.process_pending_crates_async()

            # Assert
            mock_scan.assert_called_once()
            mock_canary.assert_called_once_with(crate)
            mock_reject.assert_called_once_with(crate.path, test_findings)


@pytest.mark.asyncio
@patch("core.crate_processing_service.CrateProcessingService")
async def test_process_crates_function(mock_service_class):
    """Test the high-level process_crates function."""
    # Arrange
    mock_service = AsyncMock()
    mock_service_class.return_value = mock_service

    # Act
    await process_crates()

    # Assert
    mock_service_class.assert_called_once()
    mock_service.process_pending_crates_async.assert_called_once()
