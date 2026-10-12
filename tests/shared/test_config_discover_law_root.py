# tests/shared/test_config_discover_law_root.py
"""Law discovery passes over a directory it may not look into (ADR-170).

``sudo -u core-law core-admin law apply`` started in the governor's home
crashed at import: core-law cannot stat ``/home/darek/.intent`` and the
upward walk raised PermissionError instead of moving on.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from shared.config import (
    discover_law_root,
    resolve_default_mind_path,
    resolve_default_repo_path,
)
from shared.infrastructure.intent.law_roots import configured_repo_root


@pytest.fixture
def locked_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """cwd is a directory this process cannot look into; its parent holds law."""
    if os.geteuid() == 0:
        pytest.skip("root reads any directory")
    (tmp_path / ".intent").mkdir()
    locked = tmp_path / "home"
    locked.mkdir()
    monkeypatch.chdir(locked)
    locked.chmod(0)
    try:
        yield tmp_path
    finally:
        locked.chmod(0o755)


# ID: 0337ae3b-9b5d-4796-abec-31a7d6e4c128
def test_unreadable_cwd_is_passed_over(locked_cwd: Path) -> None:
    assert discover_law_root() == locked_cwd
    assert resolve_default_repo_path() == locked_cwd
    assert resolve_default_mind_path() == locked_cwd / ".intent"
    assert configured_repo_root() == locked_cwd
