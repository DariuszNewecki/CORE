"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/body/governance/key_management_service.py
- Symbol: keygen
- Generated: 2026-01-11 01:39:19
- 2026-06-07 (#572 Cat B batch 18): ``keygen`` no longer reads
  ``module.settings.REPO_PATH`` / ``KEY_STORAGE_DIR`` — its signature is
  now ``keygen(identity, *, path_resolver, file_service,
  allow_overwrite=False)`` and storage is derived from the injected
  ``path_resolver``. The autogen vintage mutated a module-level
  ``settings`` that no longer exists on the module. Test rewritten to
  inject mocks for the two DI parameters.
"""

from unittest.mock import MagicMock

import pytest

from body.governance.key_management_service import KeyManagementError, keygen


def test_keygen_raises_error_on_existing_key_without_overwrite(tmp_path):
    """keygen raises KeyManagementError when the target key file already
    exists and allow_overwrite is False.

    Source builds the key path as ``<repo_root>/<intent_root rel to
    repo>/keys/private.key`` (key_management_service.py:48-53). Both
    ``path_resolver.repo_root`` and ``path_resolver.intent_root`` must be
    set on the mock so the relative-to computation succeeds."""
    repo_path = tmp_path / "repo"
    intent_root = repo_path / ".intent"
    key_dir = intent_root / "keys"
    key_dir.mkdir(parents=True, exist_ok=True)
    (key_dir / "private.key").touch()

    path_resolver = MagicMock()
    path_resolver.repo_root = repo_path
    path_resolver.intent_root = intent_root
    file_service = MagicMock()

    with pytest.raises(KeyManagementError) as exc_info:
        keygen(
            "test_identity",
            path_resolver=path_resolver,
            file_service=file_service,
            allow_overwrite=False,
        )
    assert "already exists" in str(exc_info.value)
