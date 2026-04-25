# src/shared/infrastructure/rooted_repository.py

"""
RootedRepository — Shared base for read-only repositories rooted at a directory.

Provides the path-resolution surface used by IntentRepository and SpecsRepository:
- A `root` property exposing the (resolved) root path.
- `resolve_rel` which resolves a relative path against the root, rejecting
  absolute paths and any path that would escape the root via traversal.

Subclasses set the root by calling `super().__init__(<resolved Path>)`. They
remain free to add domain-specific loaders, validators, and indexes on top.

Layer: shared/infrastructure — infrastructure.
"""

from __future__ import annotations

from pathlib import Path

from shared.infrastructure.intent.errors import GovernanceError


# ID: 8d14f3a7-c625-4e9b-8a20-e3b71f0a4c92
class RootedRepository:
    """
    Base for repositories that expose read access scoped to a single root
    directory with path-traversal protection.
    """

    # ID: 9e25f4b8-d736-4f0c-9b31-f4c82a1b5d03
    def __init__(self, root: Path) -> None:
        """
        Initializes the repository with a pre-resolved root path.

        The root is stored as-is — callers are expected to pass a path
        that has already been resolved (e.g. via `Path.resolve()`).
        """
        self._root: Path = root

    @property
    # ID: af36c5e9-e847-4a1d-ac42-15d93b2c6e14
    def root(self) -> Path:
        """The resolved root directory of this repository."""
        return self._root

    # ID: ba47d6fa-f958-4b2e-bd53-26ea4c3d7f25
    def resolve_rel(self, rel: str | Path) -> Path:
        """
        Resolve a relative path against the repository root.

        Raises GovernanceError if `rel` is absolute, or if the resolved
        path escapes the root via parent traversal. The resulting path
        is guaranteed to be the root itself or strictly within it.
        """
        rel_path = Path(rel)
        if rel_path.is_absolute():
            raise GovernanceError(f"Absolute paths are not allowed: {rel_path}")

        resolved = (self._root / rel_path).resolve()
        if self._root not in resolved.parents and resolved != self._root:
            raise GovernanceError(f"Path traversal detected: {rel_path}")

        return resolved
