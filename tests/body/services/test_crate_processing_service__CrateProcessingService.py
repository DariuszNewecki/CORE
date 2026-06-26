"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/body/services/crate_processing_service.py
- Symbol: CrateProcessingService
- Generated: 2026-01-11 03:09:13
- 2026-06-07 (#572 Cat B batch 11): CrateProcessingService.__init__ now
  takes core_context. Replaced the 7 bare CrateProcessingService() calls
  with a ``service`` fixture wrapping a MagicMock-backed CoreContext.
  The tests override service.inbox_path, ._fh, .accepted_path, .repo_root,
  ._to_repo_rel, ._run_canary_validation per-case, so the fixture only
  needs to satisfy the __init__ side-effect chain (git_service.repo_path,
  file_handler) without crashing.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest
import yaml

from body.services.crate_processing_service import CrateProcessingService


@pytest.fixture
def service():
    """CrateProcessingService backed by a minimal MagicMock CoreContext.
    Construction triggers heavy setup (PathResolver, intent repo schema
    load, canary executor); the tests override every consumed attribute
    after construction, so the only requirement is that __init__ runs to
    completion."""
    ctx = MagicMock()
    ctx.git_service.repo_path = Path("/opt/dev/CORE")
    ctx.file_handler = MagicMock()
    return CrateProcessingService(ctx)


async def test_validate_crate_by_id_crate_not_found(service):
    """Test validation when crate ID doesn't exist in inbox."""
    with tempfile.TemporaryDirectory() as tmpdir:
        service.inbox_path = Path(tmpdir)
        result, findings = await service.validate_crate_by_id("non_existent_crate")
        assert not result
        assert len(findings) == 1
        assert findings[0].check_id == "infra.crate_missing"
        assert "Crate non_existent_crate missing from inbox" in findings[0].message


async def test_validate_crate_by_id_invalid_manifest_structure(service):
    """Test validation when manifest has invalid structure (fails JSON schema)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        crate_id = "test_crate_123"
        crate_path = Path(tmpdir) / crate_id
        crate_path.mkdir()
        manifest_path = crate_path / "manifest.yaml"
        manifest_path.write_text("", encoding="utf-8")
        service.inbox_path = Path(tmpdir)
        result, findings = await service.validate_crate_by_id(crate_id)
        assert not result
        assert len(findings) == 1
        assert findings[0].check_id == "infra.crate_invalid"
        assert "manifest.yaml" == findings[0].file_path


async def test_validate_crate_by_id_valid_manifest_canary_passes(service):
    """Test validation with valid manifest where canary trial passes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        crate_id = "valid_crate_456"
        crate_path = Path(tmpdir) / crate_id
        crate_path.mkdir()
        manifest = {"crate_id": crate_id, "payload_files": [], "type": "test"}
        manifest_path = crate_path / "manifest.yaml"
        manifest_path.write_text(yaml.dump(manifest), encoding="utf-8")

        async def mock_run_canary_validation(crate):
            return (True, [])

        service.inbox_path = Path(tmpdir)
        service._run_canary_validation = mock_run_canary_validation
        result, findings = await service.validate_crate_by_id(crate_id)
        assert result
        assert findings == []


async def test_apply_and_finalize_crate_success(service):
    """Test applying and finalizing an accepted crate."""
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
        service.inbox_path = inbox
        service.accepted_path = accepted
        await service.apply_and_finalize_crate(crate_id)
        assert mock_fh.write_runtime_text.call_count >= 1
        # Source's apply_and_finalize uses copy_tree + remove_tree to move
        # the crate (atomic semantics on top of FileHandler primitives); the
        # autogen vintage asserted a single ``move_tree`` call against an
        # earlier API. Track the equivalent copy+remove pair.
        mock_fh.copy_tree.assert_called_once()
        mock_fh.remove_tree.assert_called_once()


def test_to_repo_rel_with_relative_path(service):
    """Test _to_repo_rel with path inside repo root."""
    service.repo_root = Path("/fake/repo/root")
    test_path = Path("/fake/repo/root/some/subdirectory")
    result = service._to_repo_rel(test_path)
    assert result == "some/subdirectory"


def test_to_repo_rel_with_outside_path(service):
    """Test _to_repo_rel with path outside repo root."""
    service.repo_root = Path("/fake/repo/root")
    test_path = Path("/completely/different/path")
    result = service._to_repo_rel(test_path)
    assert result == "/completely/different/path"


def test_write_result_manifest(service):
    """Test _write_result_manifest creates proper result.yaml."""
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
