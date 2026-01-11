"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/body/services/crate_creation_service.py
- Symbol: CrateCreationService
- Status: 11 tests passed, some failed
- Passing tests: test_create_intent_crate_success, test_create_intent_crate_custom_type, test_create_intent_crate_empty_payload, test_create_intent_crate_path_validation_failure, test_create_intent_crate_exception_handling, test_validate_payload_paths_valid, test_validate_payload_paths_forbidden_roots, test_validate_payload_paths_traversal, test_generate_crate_id_format, test_to_repo_rel_relative, test_create_intent_crate_manifest_content
- Generated: 2026-01-11 03:12:44
"""

import pytest
import time
from pathlib import Path
from unittest.mock import Mock, AsyncMock
from body.services.crate_creation_service import CrateCreationService

class TestCrateCreationService:

    def test_validate_payload_paths_valid(self, service):
        """Test path validation with valid paths."""
        payload_files = {'src/main.py': 'code', 'tests/test_main.py': 'tests', 'config/settings.yaml': 'config'}
        errors = service.validate_payload_paths(payload_files)
        assert errors == []

    def test_validate_payload_paths_forbidden_roots(self, service):
        """Test path validation detects forbidden root directories."""
        payload_files = {'.intent/manifest.yaml': 'intent data', 'var/keys/private.pem': 'key file', 'var/cache/temp.data': 'cache data'}
        errors = service.validate_payload_paths(payload_files)
        assert len(errors) == 3
        assert all(('Constitutional boundary violation' in error for error in errors))

    def test_validate_payload_paths_traversal(self, service):
        """Test path validation detects directory traversal."""
        payload_files = {'../escape.py': 'malicious', 'src/../../root.py': 'traversal', 'normal/../parent.py': 'relative traversal'}
        errors = service.validate_payload_paths(payload_files)
        assert len(errors) == 3
        assert all(('Path traversal detected' in error for error in errors))

    def test_generate_crate_id_format(self, service):
        """Test crate ID generation format."""
        crate_id = service._generate_crate_id()
        assert crate_id.startswith('fix_')
        assert len(crate_id) == len('fix_') + 8

    def test_to_repo_rel_relative(self, service):
        """Test path conversion with relative path."""
        test_path = Path('some/relative/path')
        result = service._to_repo_rel(test_path)
        assert result == 'some/relative/path'
