# tests/body/services/test_crate_processing_service.py
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import jsonschema
import pytest
import yaml

from body.services.crate_processing_service import (
    Crate,
    CrateProcessingService,
    process_crates,
)
from shared.models.audit_models import AuditFinding


class TestCrate:
    def test_crate_initialization(self):
        """Test that Crate dataclass initializes correctly."""
        test_path = Path("/test/path")
        test_manifest = {"intent": "test", "type": "STANDARD"}
        crate = Crate(path=test_path, manifest=test_manifest)
        assert crate.path == test_path
        assert crate.manifest == test_manifest


class TestCrateProcessingService:
    @pytest.fixture
    def service(self, tmp_path):
        """Create a CrateProcessingService instance with a temporary repo root."""
        with (
            patch("body.services.crate_processing_service.settings") as mock_settings,
            patch("body.services.crate_processing_service.action_logger"),
            patch("body.services.crate_processing_service.console"),
        ):
            # THIS IS THE KEY FIX: Use tmp_path for the repo root
            mock_settings.REPO_PATH = tmp_path
            mock_settings.load.side_effect = lambda key: {
                "charter.policies.governance.intent_crate_policy": {"policy": "test"},
                "charter.schemas.constitutional.intent_crate_schema": {
                    "schema": "test"
                },
            }[key]
            # Initialize the service, which will now create its directories inside tmp_path
            return CrateProcessingService()

    def test_init_creates_directories(self, service, tmp_path):
        """Test that service initialization creates required directories inside the temp repo."""
        assert service.inbox_path.exists()
        assert service.processing_path.exists()
        assert service.accepted_path.exists()
        assert service.rejected_path.exists()
        assert str(service.inbox_path).startswith(str(tmp_path))

    @patch("body.services.crate_processing_service.settings._load_file_content")
    @patch("body.services.crate_processing_service.jsonschema.validate")
    def test_scan_and_validate_inbox_valid_crate(
        self, mock_validate, mock_load_file, service, tmp_path
    ):
        """Test scanning inbox with a valid crate."""
        crate_id = "test-crate-123"
        test_manifest = {"intent": "test intent", "type": "STANDARD"}

        crate_dir = service.inbox_path / crate_id
        crate_dir.mkdir()
        (crate_dir / "manifest.yaml").touch()

        mock_load_file.return_value = test_manifest

        result = service._scan_and_validate_inbox()

        assert len(result) == 1
        assert result[0].path == crate_dir
        assert result[0].manifest == test_manifest
        mock_validate.assert_called_once_with(
            instance=test_manifest, schema=service.crate_schema
        )

    def test_scan_and_validate_inbox_missing_manifest(self, service, tmp_path):
        """Test scanning inbox with a crate missing its manifest."""
        crate_id = "test-crate-123"
        crate_dir = service.inbox_path / crate_id
        crate_dir.mkdir()

        result = service._scan_and_validate_inbox()

        assert len(result) == 0

    @patch("body.services.crate_processing_service.settings._load_file_content")
    @patch("body.services.crate_processing_service.jsonschema.validate")
    def test_scan_and_validate_inbox_validation_error(
        self, mock_validate, mock_load_file, service, tmp_path
    ):
        """Test scanning inbox with a crate that fails schema validation."""
        crate_id = "test-crate-123"
        test_manifest = {"intent": "invalid"}

        crate_dir = service.inbox_path / crate_id
        crate_dir.mkdir()
        (crate_dir / "manifest.yaml").touch()

        mock_load_file.return_value = test_manifest
        mock_validate.side_effect = jsonschema.ValidationError("Invalid schema")

        with patch.object(service, "_move_crate_to_rejected") as mock_reject:
            result = service._scan_and_validate_inbox()
            assert len(result) == 0
            mock_reject.assert_called_once()

    def test_copy_tree_with_ignore_patterns(self, service, tmp_path):
        """Test the _copy_tree method with ignore patterns."""
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        (src / "test.py").touch()
        (src / ".git").mkdir()
        (src / "subdir").mkdir()
        (src / "subdir" / "file.txt").touch()

        ignore_patterns = [".git", "__pycache__"]

        service._copy_tree(src, dst, ignore_patterns)

        assert (dst / "test.py").exists()
        assert not (dst / ".git").exists()
        assert (dst / "subdir" / "file.txt").exists()

    def test_copy_file_creates_parents(self, service, tmp_path):
        """Test that _copy_file creates parent directories."""
        src = tmp_path / "source.txt"
        src.write_text("content")
        dst = tmp_path / "new" / "dir" / "dest.txt"

        service._copy_file(src, dst)

        assert dst.exists()
        assert dst.read_text() == "content"
        assert dst.parent.is_dir()

    @pytest.mark.asyncio
    @patch("body.services.crate_processing_service.KnowledgeGraphBuilder")
    @patch("body.services.crate_processing_service.ConstitutionalAuditor")
    async def test_run_canary_validation_success(
        self, mock_auditor_class, mock_builder_class, service, tmp_path
    ):
        """Test canary validation with a successful audit."""
        crate_path = tmp_path / "crate"
        crate_path.mkdir()
        (crate_path / "file1.py").write_text("print('ok')")

        crate = Crate(
            path=crate_path,
            manifest={"payload_files": ["file1.py"], "type": "STANDARD"},
        )

        mock_auditor = MagicMock()
        mock_auditor.run_full_audit_async = AsyncMock(return_value=[])
        mock_auditor_class.return_value = mock_auditor

        result_passed, result_findings = await service._run_canary_validation(crate)

        assert result_passed is True
        assert result_findings == []

    @pytest.mark.asyncio
    @patch("body.services.crate_processing_service.KnowledgeGraphBuilder")
    @patch("body.services.crate_processing_service.ConstitutionalAuditor")
    async def test_run_canary_validation_failure(
        self, mock_auditor_class, mock_builder_class, service, tmp_path
    ):
        """Test canary validation with a failed audit."""
        crate_path = tmp_path / "crate"
        crate_path.mkdir()
        (crate_path / "file1.py").write_text("bad code")

        crate = Crate(
            path=crate_path,
            manifest={"payload_files": ["file1.py"], "type": "STANDARD"},
        )

        test_findings = [
            {"check_id": "test.fail", "severity": "error", "message": "fail"}
        ]
        mock_auditor = MagicMock()
        mock_auditor.run_full_audit_async = AsyncMock(return_value=test_findings)
        mock_auditor_class.return_value = mock_auditor

        result_passed, result_findings = await service._run_canary_validation(crate)

        assert result_passed is False
        assert len(result_findings) == 1
        assert isinstance(result_findings[0], AuditFinding)
        assert result_findings[0].severity == "error"

    def test_apply_accepted_crate_standard_type(self, service, tmp_path):
        """Test applying an accepted crate with STANDARD type."""
        crate_path = tmp_path / "crate"
        crate_path.mkdir()
        (crate_path / "src").mkdir(exist_ok=True)
        (crate_path / "src" / "file1.py").write_text("content1")

        crate = Crate(
            path=crate_path,
            manifest={"payload_files": ["src/file1.py"], "type": "STANDARD"},
        )

        service._apply_accepted_crate(crate)

        assert (service.repo_root / "src" / "file1.py").exists()
        assert (service.repo_root / "src" / "file1.py").read_text() == "content1"

    def test_apply_accepted_crate_constitutional_amendment(self, service, tmp_path):
        """Test applying a CONSTITUTIONAL_AMENDMENT crate."""
        crate_path = tmp_path / "crate"
        crate_path.mkdir()
        (crate_path / "policy.yaml").write_text("rules: []")

        crate = Crate(
            path=crate_path,
            manifest={
                "payload_files": ["policy.yaml"],
                "type": "CONSTITUTIONAL_AMENDMENT",
            },
        )

        service._apply_accepted_crate(crate)

        expected_path = (
            service.repo_root / ".intent/charter/policies/governance/policy.yaml"
        )
        assert expected_path.exists()
        assert expected_path.read_text() == "rules: []"

    def test_write_result_manifest_with_string_details(self, service, tmp_path):
        """Test writing a result manifest with string details."""
        crate_path = tmp_path / "my-crate"
        crate_path.mkdir()

        service._write_result_manifest(crate_path, "accepted", "It passed.")

        result_file = crate_path / "result.yaml"
        assert result_file.exists()
        data = yaml.safe_load(result_file.read_text())
        assert data["status"] == "accepted"
        assert data["justification"] == "It passed."
        assert "processed_at_utc" in data

    def test_write_result_manifest_with_list_details(self, service, tmp_path):
        """Test writing result manifest with list of findings."""
        crate_path = tmp_path / "my-crate"
        crate_path.mkdir()
        findings = [
            AuditFinding(check_id="f1", severity="error", message="Test violation 1"),
            AuditFinding(check_id="f2", severity="warning", message="Test violation 2"),
        ]

        service._write_result_manifest(crate_path, "rejected", findings)

        result_file = crate_path / "result.yaml"
        assert result_file.exists()
        data = yaml.safe_load(result_file.read_text())
        assert data["status"] == "rejected"
        assert len(data["violations"]) == 2
        assert data["violations"][0]["check_id"] == "f1"

    @pytest.mark.asyncio
    async def test_process_pending_crates_async_no_crates(self, service):
        """Test processing when no valid crates are found."""
        with patch.object(
            service, "_scan_and_validate_inbox", return_value=[]
        ) as mock_scan:
            await service.process_pending_crates_async()
            mock_scan.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_pending_crates_async_flow(self, service, tmp_path, mocker):
        """Test the full processing flow for a successful and a failed crate."""
        mocker.patch.object(Path, "rename")  # Mock rename to avoid moving dirs
        mocker.patch.object(service, "_write_result_manifest")
        mocker.patch.object(service, "_apply_accepted_crate")

        crate1_path = service.inbox_path / "crate1"
        crate1 = Crate(path=crate1_path, manifest={"type": "STANDARD"})
        crate2_path = service.inbox_path / "crate2"
        crate2 = Crate(path=crate2_path, manifest={"type": "STANDARD"})
        mocker.patch.object(
            service, "_scan_and_validate_inbox", return_value=[crate1, crate2]
        )

        mock_canary_validation = mocker.patch.object(
            service, "_run_canary_validation", new_callable=AsyncMock
        )
        mock_canary_validation.side_effect = [
            (True, []),
            (
                False,
                [AuditFinding(check_id="fail", severity="error", message="failed")],
            ),
        ]

        await service.process_pending_crates_async()

        assert mock_canary_validation.call_count == 2
        service._apply_accepted_crate.assert_called_once_with(crate1)


@pytest.mark.asyncio
@patch("body.services.crate_processing_service.CrateProcessingService")
async def test_process_crates_function(mock_service_class):
    """Test the high-level process_crates function."""
    mock_service_instance = MagicMock()
    mock_service_instance.process_pending_crates_async = AsyncMock()
    mock_service_class.return_value = mock_service_instance

    await process_crates()

    mock_service_class.assert_called_once()
    mock_service_instance.process_pending_crates_async.assert_awaited_once()
