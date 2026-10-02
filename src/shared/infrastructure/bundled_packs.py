# src/shared/infrastructure/bundled_packs.py

"""Bundled governance-pack registry resolver.

The published ``core-runtime`` wheel carries the open governance packs as
package data under ``shared._packs`` -- the wheel-side mirror of the
repository's top-level ``packs/`` registry (ADR-149). This module is the only
place that names that package. Precedence is **repository first, bundle
second**, the same rule the prompt corpus follows (#909): a CORE source
checkout reads its own ``packs/``; a ``pip install core-runtime`` user, whose
repository has no ``packs/``, reads the bundle.

Callers that need files on disk take :func:`pack_registry_dir`, whose lifetime
bounds any temporary extraction (an installed wheel resolves in place, a
zipimported one is extracted). The bundle is never a write destination.

Pure functions; no ``get_intent_repository()`` and no settings import, so this
is usable before bootstrap.
"""

from __future__ import annotations

import importlib.resources
from collections.abc import Iterator
from contextlib import contextmanager
from importlib.resources.abc import Traversable
from pathlib import Path


_PACKS_PACKAGE = "shared._packs"
_REPO_PACKS_DIRNAME = "packs"

# Package-only files that are not pack payload (parity and listings skip them).
_PACKAGE_MARKERS = frozenset({"__init__.py"})


# ID: 774dc8cd-d643-4898-aea6-9a01edf342e3
def bundled_packs_root() -> Traversable:
    """The bundled pack registry as a ``Traversable`` directory."""
    return importlib.resources.files(_PACKS_PACKAGE)


# ID: ee5b8494-9b14-43ec-a53f-b27cb49de6b0
def is_package_marker(relative_path: str) -> bool:
    """True for files that exist only to make the mirror importable."""
    return Path(relative_path).name in _PACKAGE_MARKERS


@contextmanager
# ID: b063d32b-0a47-469e-905a-b5c9d1d05e7b
def bundled_packs_as_path() -> Iterator[Path]:
    """The bundled registry materialised as a real directory, for the block.

    Read-only by contract; the path is valid only inside the ``with`` block.
    """
    with importlib.resources.as_file(bundled_packs_root()) as path:
        yield path


@contextmanager
# ID: e1fc6810-be7c-4c0f-91b9-5c31252e4b96
def pack_registry_dir(repo_root: Path) -> Iterator[Path]:
    """The pack registry directory to read, repository first, bundle second.

    ``repo_root`` is the repository that owns the law root (the parent of
    ``.intent/``). When it carries a ``packs/`` directory -- a CORE source
    checkout -- that directory is the registry. Otherwise the bundled
    registry shipped with the installed ``core-runtime`` is used.
    """
    repo_packs = Path(repo_root) / _REPO_PACKS_DIRNAME
    if repo_packs.is_dir():
        yield repo_packs
        return
    with bundled_packs_as_path() as path:
        yield path


__all__ = [
    "bundled_packs_as_path",
    "bundled_packs_root",
    "is_package_marker",
    "pack_registry_dir",
]
