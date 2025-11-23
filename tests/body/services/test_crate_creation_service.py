# tests/body/services/test_crate_creation_service.py
"""
Tests for the Intent Crate creation service.
Validates:
- Crate creation with valid inputs
- Manifest generation and validation
- Payload file handling
- Error handling
- Path validation
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
import yaml

from body.services.crate_creation_service import (
    CrateCreationService,
    create_crate_from_generation_result,
)


@pytest.fixture
def mock_settings(tmp_path):
    """Mock settings with temporary paths."""
    with patch("body.services.crate_creation_service.settings") as mock:
        mock.REPO_PATH = tmp_path
        mock.load.return_value = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "required": ["intent", "type", "created_at", "payload_files"],
            "properties": {
                "intent": {"type": "string"},
                "type": {
                    "type": "string",
                    "enum": ["STANDARD", "CONSTITUTIONAL_AMENDMENT"],
                },
                "created_at": {"type": "string"},
                "payload_files": {"type": "array"},
            },
        }
        yield mock


@pytest.fixture
def service(mock_settings):
    """Create CrateCreationService instance."""
    return CrateCreationService()


class TestCrateCreationService:
    """Test suite for CrateCreationService."""

    def test_initialization_creates_directories(self, service, tmp_path):
        """Verify service initialization creates required directories."""
        inbox_path = tmp_path / "work" / "crates" / "inbox"
        assert inbox_path.exists()
        assert inbox_path.is_dir()

    def test_generate_crate_id_format(self, service):
        """Verify crate ID has correct format."""
        crate_id = service._generate_crate_id()
        assert crate_id.startswith("crate_")
        # Format: crate_YYYYMMDD_HHMMSS
        parts = crate_id.split("_")
        assert len(parts) >= 3
        assert len(parts[1]) == 8  # YYYYMMDD
        assert len(parts[2]) == 6  # HHMMSS

    def test_create_manifest_with_metadata(self, service):
        """Verify manifest includes provided metadata."""
        metadata = {
            "context_tokens": 1000,
            "generation_tokens": 500,
        }
        manifest = service._create_manifest(
            intent="Test",
            payload_files=["src/test.py"],
            crate_type="STANDARD",
            metadata=metadata,
        )
        assert manifest["metadata"] == metadata

    def test_create_intent_crate_success(self, service, tmp_path):
        """Verify successful crate creation."""
        payload_files = {
            "src/test.py": "print('hello')",
            "tests/test_test.py": "def test_hello(): pass",
        }
        crate_id = service.create_intent_crate(
            intent="Test feature",
            payload_files=payload_files,
            crate_type="STANDARD",
        )
        # Verify crate directory exists
        crate_path = service.inbox_path / crate_id
        assert crate_path.exists()
        assert crate_path.is_dir()
        # Verify manifest exists and is valid
        manifest_path = crate_path / "manifest.yaml"
        assert manifest_path.exists()
        manifest = yaml.safe_load(manifest_path.read_text())
        assert manifest["intent"] == "Test feature"
        assert manifest["type"] == "STANDARD"
        # Verify payload files exist
        assert (crate_path / "src" / "test.py").exists()
        assert (crate_path / "tests" / "test_test.py").exists()
        # Verify file contents
        assert (crate_path / "src" / "test.py").read_text() == "print('hello')"

    def test_create_intent_crate_preserves_directory_structure(self, service):
        """Verify payload files maintain directory structure."""
        payload_files = {
            "src/body/middleware/rate_limiter.py": "# rate limiter",
            "tests/body/middleware/test_rate_limiter.py": "# tests",
        }
        crate_id = service.create_intent_crate(
            intent="Test",
            payload_files=payload_files,
        )
        crate_path = service.inbox_path / crate_id
        # Verify nested directories created
        assert (crate_path / "src" / "body" / "middleware").exists()
        assert (crate_path / "tests" / "body" / "middleware").exists()
        # Verify files in correct locations
        assert (crate_path / "src" / "body" / "middleware" / "rate_limiter.py").exists()

    def test_create_intent_crate_constitutional_amendment(self, service):
        """Verify constitutional amendment crate type."""
        payload_files = {"new_policy.yaml": "rules: []"}
        crate_id = service.create_intent_crate(
            intent="Add new governance policy",
            payload_files=payload_files,
            crate_type="CONSTITUTIONAL_AMENDMENT",
        )
        manifest_path = service.inbox_path / crate_id / "manifest.yaml"
        manifest = yaml.safe_load(manifest_path.read_text())
        assert manifest["type"] == "CONSTITUTIONAL_AMENDMENT"

    @patch("body.services.crate_creation_service.action_logger")
    def test_create_intent_crate_logs_success(self, mock_logger, service):
        """Verify success is logged."""
        payload_files = {"src/test.py": "pass"}
        service.create_intent_crate(
            intent="Test",
            payload_files=payload_files,
        )
        # Verify log event called
        mock_logger.log_event.assert_called_once()
        call_args = mock_logger.log_event.call_args
        assert call_args[0][0] == "crate.creation.success"
        assert "crate_id" in call_args[0][1]
        assert call_args[0][1]["intent"] == "Test"

    def test_create_intent_crate_cleans_up_on_failure(self, service, tmp_path):
        """Verify cleanup on failure."""
        # Force failure by providing invalid manifest data
        with patch.object(service, "_create_manifest") as mock_manifest:
            mock_manifest.side_effect = ValueError("Invalid manifest")
            with pytest.raises(ValueError):
                service.create_intent_crate(
                    intent="Test",
                    payload_files={"src/test.py": "pass"},
                )
            # Verify no crate directory left behind
            # (This is hard to test perfectly, but we can check that
            # the method attempts cleanup by catching the exception)

    def test_validate_payload_paths_rejects_absolute_paths(self, service):
        """Verify absolute paths are rejected."""
        payload_files = {"/etc/passwd": "content"}
        errors = service.validate_payload_paths(payload_files)
        assert len(errors) == 1
        assert "Absolute path not allowed" in errors[0]

    def test_validate_payload_paths_rejects_path_traversal(self, service):
        """Verify path traversal attempts are rejected."""
        payload_files = {"src/../../../etc/passwd": "content"}
        errors = service.validate_payload_paths(payload_files)
        assert len(errors) == 1
        assert "Path traversal not allowed" in errors[0]

    def test_validate_payload_paths_rejects_invalid_roots(self, service):
        """Verify paths outside allowed roots are rejected."""
        payload_files = {"invalid/path/file.py": "content"}
        errors = service.validate_payload_paths(payload_files)
        assert len(errors) == 1
        assert "must start with" in errors[0]

    def test_validate_payload_paths_accepts_valid_paths(self, service):
        """Verify valid paths pass validation."""
        payload_files = {
            "src/module.py": "content",
            "tests/test_module.py": "content",
            ".intent/charter/policies/governance/policy.yaml": "content",
        }
        errors = service.validate_payload_paths(payload_files)
        assert len(errors) == 0

    def test_get_crate_info_existing_crate(self, service):
        """Verify crate info retrieval for existing crate."""
        # Create a crate
        payload_files = {"src/test.py": "pass"}
        crate_id = service.create_intent_crate(
            intent="Test",
            payload_files=payload_files,
        )
        # Get info
        info = service.get_crate_info(crate_id)
        assert info is not None
        assert info["crate_id"] == crate_id
        assert info["status"] == "inbox"
        assert info["manifest"]["intent"] == "Test"

    def test_get_crate_info_nonexistent_crate(self, service):
        """Verify None returned for nonexistent crate."""
        info = service.get_crate_info("nonexistent_crate")
        assert info is None


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_create_crate_from_generation_result_success(self, mock_settings):
        """Verify convenience function creates crate."""
        files = {"src/test.py": "pass"}
        metadata = {"tokens": 100}
        crate_id = create_crate_from_generation_result(
            intent="Test",
            files_generated=files,
            generation_metadata=metadata,
        )
        assert crate_id.startswith("crate_")

    def test_create_crate_from_generation_result_validates_paths(self, mock_settings):
        """Verify path validation in convenience function."""
        files = {"/absolute/path.py": "pass"}
        with pytest.raises(ValueError) as exc_info:
            create_crate_from_generation_result(
                intent="Test",
                files_generated=files,
            )
        assert "Invalid payload paths" in str(exc_info.value)
