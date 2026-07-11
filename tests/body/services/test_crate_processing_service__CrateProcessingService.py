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

import os
import shutil
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest
import yaml

from body.services.crate_processing_service import Crate, CrateProcessingService


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


async def test_run_canary_validation_snapshot_preserves_symlinks(
    service, monkeypatch, tmp_path
):
    """Regression test for the sandbox-ballooning bug (2026-07-11): the repo
    snapshot step must copy a real symlink (e.g. the repo-root ``ITAM ->
    /mnt/vector_db/YPTO/ITAM`` link) as a symlink, not dereference it and
    copy the target directory's full content. That dereferencing turned two
    ~6M sandboxes into 1.3G each. See
    src/body/services/crate_processing_service.py:174
    (``shutil.copytree(..., symlinks=True, ...)``).
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    real_target = tmp_path / "external_target"
    real_target.mkdir()
    (real_target / "big_file.txt").write_text("x" * 1000, encoding="utf-8")
    (repo_root / "linked_dir").symlink_to(real_target, target_is_directory=True)

    service.repo_root = repo_root

    # The method's `finally` always rmtrees the sandbox; suppress that so the
    # snapshot survives long enough to inspect.
    monkeypatch.setattr(shutil, "rmtree", lambda *a, **k: None)

    # Short-circuit everything past the snapshot step (KG build / audit /
    # canary_executor.enforce) — only section A's copytree needs to run for
    # real. The resulting exception is caught by the method's own
    # `except Exception` and turned into a harmless infra.canary_crash finding.
    monkeypatch.setattr(
        "body.services.crate_processing_service.KnowledgeGraphBuilder",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("stop after snapshot")),
    )

    crate = Crate(
        path=tmp_path / "crate",
        manifest={"crate_id": "sym_test", "payload_files": []},
    )
    await service._run_canary_validation(crate)

    copied_link = repo_root / "work" / "canary" / "sandbox_sym_test" / "linked_dir"
    assert copied_link.is_symlink(), "sandbox copy of a symlinked dir must remain a symlink"
    assert copied_link.resolve() == real_target.resolve()


async def test_apply_and_finalize_crate_success(service):
    """Test applying and finalizing an accepted crate.

    After #706: crate is deleted from inbox after applying (no move to
    accepted/). Expects write_runtime_text for payload, remove_tree for
    cleanup, and NO copy_tree call.
    """
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
        mock_fh = Mock()
        service._fh = mock_fh
        service.inbox_path = inbox
        await service.apply_and_finalize_crate(crate_id)
        assert mock_fh.write_runtime_text.call_count >= 1
        mock_fh.remove_tree.assert_called_once()
        mock_fh.copy_tree.assert_not_called()


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


def test_purge_stale_inbox_crates_removes_old_crate(service):
    """Crates whose manifest.yaml mtime exceeds ttl_days are purged."""
    with tempfile.TemporaryDirectory() as tmpdir:
        inbox = Path(tmpdir)
        service.inbox_path = inbox
        mock_fh = Mock()
        service._fh = mock_fh
        service._to_repo_rel = lambda p: str(p)

        old_crate = inbox / "old_crate_001"
        old_crate.mkdir()
        manifest = old_crate / "manifest.yaml"
        manifest.write_text("crate_id: old_crate_001\n", encoding="utf-8")
        old_mtime = time.time() - (8 * 86400)
        os.utime(manifest, (old_mtime, old_mtime))

        purged = service.purge_stale_inbox_crates(ttl_days=7)
        assert purged == ["old_crate_001"]
        mock_fh.remove_tree.assert_called_once()


def test_purge_stale_inbox_crates_keeps_fresh_crate(service):
    """Crates younger than ttl_days are not purged."""
    with tempfile.TemporaryDirectory() as tmpdir:
        inbox = Path(tmpdir)
        service.inbox_path = inbox
        mock_fh = Mock()
        service._fh = mock_fh
        service._to_repo_rel = lambda p: str(p)

        fresh_crate = inbox / "fresh_crate_001"
        fresh_crate.mkdir()
        manifest = fresh_crate / "manifest.yaml"
        manifest.write_text("crate_id: fresh_crate_001\n", encoding="utf-8")

        purged = service.purge_stale_inbox_crates(ttl_days=7)
        assert purged == []
        mock_fh.remove_tree.assert_not_called()


def test_purge_stale_inbox_crates_nonexistent_inbox(service):
    """Returns empty list when inbox directory does not exist."""
    service.inbox_path = Path("/nonexistent/inbox/path/that/does/not/exist")
    purged = service.purge_stale_inbox_crates()
    assert purged == []
