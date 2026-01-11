"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/mind/governance/key_management_service.py
- Symbol: keygen
- Status: 1 tests passed, some failed
- Passing tests: test_keygen_raises_error_on_existing_key_without_overwrite
- Generated: 2026-01-11 01:39:19
"""

import pytest
from mind.governance.key_management_service import keygen
import os
import tempfile
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

def test_keygen_raises_error_on_existing_key_without_overwrite(tmp_path):
    """Test that keygen raises KeyManagementError if key exists and allow_overwrite is False."""
    identity = 'test_identity'
    repo_path = tmp_path / 'repo'
    key_dir = repo_path / '.intent' / 'keys'
    key_file = key_dir / 'private.key'
    key_file.parent.mkdir(parents=True, exist_ok=True)
    key_file.touch()
    import mind.governance.key_management_service as module
    original_repo_path = module.settings.REPO_PATH
    original_key_dir = module.settings.KEY_STORAGE_DIR
    try:
        module.settings.REPO_PATH = Path(repo_path)
        module.settings.KEY_STORAGE_DIR = Path(key_dir)
        with pytest.raises(Exception) as exc_info:
            keygen(identity, allow_overwrite=False)
        assert 'already exists' in str(exc_info.value)
    finally:
        module.settings.REPO_PATH = original_repo_path
        module.settings.KEY_STORAGE_DIR = original_key_dir
