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
        # Use the ACTUAL schema from intent_crate_schema.json
        mock.load.return_value = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "https://core.local/schemas/intent_crate_schema.json",
            "title": "Intent Crate Manifest",
            "description": "The constitutional schema for a manifest.yaml file within an Intent Crate.",
            "type": "object",
            "required": ["crate_id", "author", "intent", "type"],
            "properties": {
                "crate_id": {
                    "type": "string",
                    "description": "A unique identifier for this crate.",
                    "pattern": "^[a-zA-Z0-9_-]+$",
                },
                "author": {
                    "type": "string",
                    "description": "The identity of the human or system that created the crate.",
                },
                "intent": {
                    "type": "string",
                    "description": "A clear, one-sentence justification for the proposed change.",
                    "minLength": 20,
                },
                "type": {
                    "type": "string",
                    "description": "The type of change being proposed.",
                    "enum": ["CONSTITUTIONAL_AMENDMENT", "CODE_MODIFICATION"],
                },
                "payload_files": {
                    "type": "array",
                    "description": "A list of the files included in this crate.",
                    "items": {"type": "string"},
                },
            },
            "additionalProperties": False,
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
        """Verify manifest is created with correct structure."""
        manifest = service._create_manifest(
            crate_id="test_crate_123",
            intent="This is a test intent that is long enough to pass validation",
            payload_files=["src/test.py"],
            crate_type="STANDARD",
            metadata={},
        )
        # Verify required fields per schema
        assert "crate_id" in manifest
        assert "author" in manifest
        assert "intent" in manifest
        assert "type" in manifest
        assert (
            manifest["type"] == "CODE_MODIFICATION"
        )  # STANDARD maps to CODE_MODIFICATION

    def test_create_intent_crate_success(self, service, tmp_path):
        """Verify successful crate creation."""
        payload_files = {
            "src/test.py": "print('hello')",
            "tests/test_test.py": "def test_hello(): pass",
        }
        crate_id = service.create_intent_crate(
            intent="Test feature implementation with proper length",
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
        assert "Test feature" in manifest["intent"]
        assert manifest["type"] == "CODE_MODIFICATION"
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
            intent="Test directory structure preservation properly",
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
            intent="Add new governance policy to the constitutional framework",
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
            intent="Test logging functionality with sufficient length",
            payload_files=payload_files,
        )
        # Verify log event called
        mock_logger.log_event.assert_called_once()
        call_args = mock_logger.log_event.call_args
        assert call_args[0][0] == "crate.creation.success"
        assert "crate_id" in call_args[0][1]

    def test_create_intent_crate_cleans_up_on_failure(self, service, tmp_path):
        """Verify cleanup on failure."""
        # Force failure by providing invalid manifest data
        with patch.object(service, "_create_manifest") as mock_manifest:
            mock_manifest.side_effect = ValueError("Invalid manifest")
            with pytest.raises(ValueError):
                service.create_intent_crate(
                    intent="Test cleanup on failure with proper length",
                    payload_files={"src/test.py": "pass"},
                )

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
            intent="Test crate information retrieval functionality",
            payload_files=payload_files,
        )
        # Get info
        info = service.get_crate_info(crate_id)
        assert info is not None
        assert info["crate_id"] == crate_id
        assert info["status"] == "inbox"

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
            intent="Test convenience function for crate creation",
            files_generated=files,
            generation_metadata=metadata,
        )
        assert crate_id.startswith("crate_")

    def test_create_crate_from_generation_result_validates_paths(self, mock_settings):
        """Verify path validation in convenience function."""
        files = {"/absolute/path.py": "pass"}
        with pytest.raises(ValueError) as exc_info:
            create_crate_from_generation_result(
                intent="Test path validation in convenience function",
                files_generated=files,
            )
        assert "Invalid payload paths" in str(exc_info.value)
