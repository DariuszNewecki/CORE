"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/body/services/crate_processing_service.py
- Symbol: CrateProcessingService
- Status: 7 tests passed, some failed
- Passing tests: test_validate_crate_by_id_crate_not_found, test_validate_crate_by_id_invalid_manifest_structure, test_validate_crate_by_id_valid_manifest_canary_passes, test_apply_and_finalize_crate_success, test_to_repo_rel_with_relative_path, test_to_repo_rel_with_outside_path, test_write_result_manifest
- Generated: 2026-01-11 03:09:13
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml

from body.services.crate_processing_service import CrateProcessingService


@pytest.mark.asyncio
async def test_validate_crate_by_id_crate_not_found():
    """Test validation when crate ID doesn't exist in inbox."""
    service = CrateProcessingService()
    with tempfile.TemporaryDirectory() as tmpdir:
        service.inbox_path = Path(tmpdir)
        result, findings = await service.validate_crate_by_id("non_existent_crate")
        assert not result
        assert len(findings) == 1
        assert findings[0].check_id == "infra.crate_missing"
        assert "Crate non_existent_crate missing from inbox" in findings[0].message


@pytest.mark.asyncio
async def test_validate_crate_by_id_invalid_manifest_structure():
    """Test validation when manifest has invalid structure (fails JSON schema)."""
    service = CrateProcessingService()
    with tempfile.TemporaryDirectory() as tmpdir:
        crate_id = "test_crate_123"
        crate_path = Path(tmpdir) / crate_id
        crate_path.mkdir()
        manifest_path = crate_path / "manifest.yaml"
        manifest_path.write_text("", encoding="utf-8")
        original_inbox = service.inbox_path
        service.inbox_path = Path(tmpdir)
        try:
            result, findings = await service.validate_crate_by_id(crate_id)
            assert not result
            assert len(findings) == 1
            assert findings[0].check_id == "infra.crate_invalid"
            assert "manifest.yaml" == findings[0].file_path
        finally:
            service.inbox_path = original_inbox


@pytest.mark.asyncio
async def test_validate_crate_by_id_valid_manifest_canary_passes():
    """Test validation with valid manifest where canary trial passes."""
    service = CrateProcessingService()
    with tempfile.TemporaryDirectory() as tmpdir:
        crate_id = "valid_crate_456"
        crate_path = Path(tmpdir) / crate_id
        crate_path.mkdir()
        manifest = {"crate_id": crate_id, "payload_files": [], "type": "test"}
        manifest_path = crate_path / "manifest.yaml"
        manifest_path.write_text(yaml.dump(manifest), encoding="utf-8")

        async def mock_run_canary_validation(crate):
            return (True, [])

        original_inbox = service.inbox_path
        service.inbox_path = Path(tmpdir)
        original_method = service._run_canary_validation
        service._run_canary_validation = mock_run_canary_validation
        try:
            result, findings = await service.validate_crate_by_id(crate_id)
            assert result
            assert findings == []
        finally:
            service.inbox_path = original_inbox
            service._run_canary_validation = original_method


@pytest.mark.asyncio
async def test_apply_and_finalize_crate_success():
    """Test applying and finalizing an accepted crate."""
    service = CrateProcessingService()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        crate_id = "crate_to_apply"
        inbox = tmp_path / "inbox"
        inbox.mkdir()
        crate_path = inbox / crate_id
        crate_path.mkdir()
        manifest = {"crate_id": crate_id, "payload_files": ["test_file.txt"]}
        manifest_path = crate_path / "manifest.yaml"
        manifest_path.write_text(yaml.dump(manifest), encoding="utf-8")
        payload_file = crate_path / "test_file.txt"
        payload_file.write_text("Test content", encoding="utf-8")
        accepted = tmp_path / "accepted"
        accepted.mkdir()
        mock_fh = Mock()
        service._fh = mock_fh
        original_inbox = service.inbox_path
        original_accepted = service.accepted_path
        service.inbox_path = inbox
        service.accepted_path = accepted
        try:
            await service.apply_and_finalize_crate(crate_id)
            assert mock_fh.write_runtime_text.call_count >= 1
            mock_fh.move_tree.assert_called_once()
        finally:
            service.inbox_path = original_inbox
            service.accepted_path = original_accepted


def test_to_repo_rel_with_relative_path():
    """Test _to_repo_rel with path inside repo root."""
    service = CrateProcessingService()
    service.repo_root = Path("/fake/repo/root")
    test_path = Path("/fake/repo/root/some/subdirectory")
    result = service._to_repo_rel(test_path)
    assert result == "some/subdirectory"


def test_to_repo_rel_with_outside_path():
    """Test _to_repo_rel with path outside repo root."""
    service = CrateProcessingService()
    service.repo_root = Path("/fake/repo/root")
    test_path = Path("/completely/different/path")
    result = service._to_repo_rel(test_path)
    assert result == "/completely/different/path"


def test_write_result_manifest():
    """Test _write_result_manifest creates proper result.yaml."""
    service = CrateProcessingService()
    with tempfile.TemporaryDirectory() as tmpdir:
        crate_path = Path(tmpdir) / "test_crate"
        crate_path.mkdir()
        mock_fh = Mock()
        service._fh = mock_fh
        service._to_repo_rel = lambda p: "relative/path"
        service._write_result_manifest(crate_path, "accepted", "Test details")
        mock_fh.write_runtime_text.assert_called_once()
        call_args = mock_fh.write_runtime_text.call_args
        assert call_args[0][0] == "relative/path/result.yaml"
        content = call_args[0][1]
        assert "status: accepted" in content
        assert "Test details" in content
        assert "processed_at_utc" in content
