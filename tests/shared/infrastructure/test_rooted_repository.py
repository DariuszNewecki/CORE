"""Issue #128: dedup of root + resolve_rel between IntentRepository and
SpecsRepository.

Verifies the canonical implementation now lives on RootedRepository:
- root accessor returns the configured _root
- resolve_rel rejects absolute paths
- resolve_rel rejects traversal escapes from root
"""

from __future__ import annotations

from pathlib import Path

import pytest

from shared.infrastructure.intent.errors import GovernanceError
from shared.infrastructure.rooted_repository import RootedRepository


class _Probe(RootedRepository):
    def __init__(self, root: Path) -> None:
        self._root = root.resolve()


# ID: 79203cc7-57f4-4ce8-a455-55158e57ec0c
def test_root_returns_configured_path(tmp_path: Path) -> None:
    probe = _Probe(tmp_path)
    assert probe.root == tmp_path.resolve()


# ID: ce7a5560-884f-4f81-a616-7f773072fe97
def test_resolve_rel_resolves_safe_relative_path(tmp_path: Path) -> None:
    probe = _Probe(tmp_path)
    (tmp_path / "sub").mkdir()
    resolved = probe.resolve_rel("sub/file.yaml")
    assert resolved == (tmp_path / "sub" / "file.yaml").resolve()


# ID: 9d0c14e6-25e0-4757-b138-473996ca0625
def test_resolve_rel_rejects_absolute_and_traversal(tmp_path: Path) -> None:
    probe = _Probe(tmp_path)

    with pytest.raises(GovernanceError, match="Absolute paths"):
        probe.resolve_rel("/etc/passwd")

    with pytest.raises(GovernanceError, match="Path traversal"):
        probe.resolve_rel("../escaped.txt")
