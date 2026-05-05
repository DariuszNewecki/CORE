# src/shared/infrastructure/rooted_repository.py

"""
RootedRepository — base for read-only repositories rooted at a filesystem path
with traversal-safe resolution.

Subclasses are responsible for assigning ``self._root: Path`` in their own
``__init__``. This base provides the canonical ``root`` property and a
boundary-enforced ``resolve_rel`` that rejects absolute paths and detects
traversal escapes — duplicated in IntentRepository and SpecsRepository before
issue #128.
"""

from __future__ import annotations

from pathlib import Path

from shared.infrastructure.intent.errors import GovernanceError


# ID: e5d091b0-d8f3-492a-bc05-781775c4440b
class RootedRepository:
    """
    Base for repositories rooted at a filesystem path.

    Contract:
    - Subclass __init__ MUST assign ``self._root: Path`` before any method
      call; the base class does not initialize it.
    - ``resolve_rel`` rejects absolute paths and traversal escapes from the
      root, raising GovernanceError with stable messages.
    """

    _root: Path

    @property
    # ID: 1fe51e0a-fb21-4791-9894-a51f77217fea
    def root(self) -> Path:
        return self._root

    # ID: 2c73489f-f53f-4130-b74e-c026c42fd90d
    def resolve_rel(self, rel: str | Path) -> Path:
        rel_path = Path(rel)
        if rel_path.is_absolute():
            raise GovernanceError(f"Absolute paths are not allowed: {rel_path}")

        resolved = (self._root / rel_path).resolve()
        if self._root not in resolved.parents and resolved != self._root:
            raise GovernanceError(f"Path traversal detected: {rel_path}")

        return resolved
