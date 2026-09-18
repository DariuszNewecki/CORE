# src/shared/infrastructure/bundled_prompts.py

"""Bundled prompt corpus resolver (#909).

The published ``core-runtime`` wheel carries the prompt corpus as package
data under ``shared._prompts`` -- the wheel-side mirror of the repository's
prompt root (``PathResolver.prompts_dir``). This module is the only place
that names that package. Precedence everywhere is **repository first,
bundle second**: a consumer looks at the repository's prompt root and falls
back here only when the repository does not carry the artifact, so an
adopter's own prompts always win and a missing artifact still surfaces as
the loader's ordinary ``FileNotFoundError`` rather than as unrelated content.

Resources are read through ``importlib.resources`` ``Traversable`` objects.
A Traversable is not promised to be a filesystem ``Path`` (an installed wheel
is, a zipimported one is not), so callers that only need to *read* use the
Traversable directly (``is_file`` / ``read_text``), and callers that
genuinely need files on disk take :func:`bundled_prompts_as_path`, whose
lifetime bounds any temporary extraction. The bundle is never a write
destination.

Pure functions; no ``get_intent_repository()`` and no settings import, so
this is usable before bootstrap.
"""

from __future__ import annotations

import importlib.resources
from collections.abc import Iterator
from contextlib import contextmanager
from importlib.resources.abc import Traversable
from pathlib import Path


_PROMPTS_PACKAGE = "shared._prompts"

# Package-only files that are not prompt payload (parity and listings skip them).
_PACKAGE_MARKERS = frozenset({"__init__.py"})


# ID: d62f5e9f-8dc1-4781-a41a-55ad287e826a
def bundled_prompts_root() -> Traversable:
    """The bundled prompt corpus as a ``Traversable`` directory."""
    return importlib.resources.files(_PROMPTS_PACKAGE)


# ID: 69dea0d9-d009-4eda-8112-58f4f941d973
def bundled_prompt(name: str) -> Traversable | None:
    """The bundled artifact directory or loose prompt file called *name*.

    ``name`` is a single path component (``docstring_writer``,
    ``capability_definer.prompt``). Returns ``None`` when the bundle does not
    carry it, when *name* is a package marker, or when it is not a single
    component -- never a best-effort neighbour.
    """
    if not name or name in _PACKAGE_MARKERS or "/" in name or "\\" in name:
        return None
    if name in {".", ".."}:
        return None
    candidate = bundled_prompts_root().joinpath(name)
    if candidate.is_file() or candidate.is_dir():
        return candidate
    return None


# ID: 60007f90-316a-4f2a-9748-e8a9d2d6630b
def is_package_marker(relative_path: str) -> bool:
    """True for files that exist only to make the mirror importable."""
    return Path(relative_path).name in _PACKAGE_MARKERS


@contextmanager
# ID: f69a575d-55e3-458e-b557-dd204befd7d6
def bundled_prompts_as_path() -> Iterator[Path]:
    """The bundled corpus materialised as a real directory, for the block.

    ``importlib.resources.as_file`` returns the package directory itself for
    an installed wheel and a temporary extraction otherwise; either way the
    path is valid only inside the ``with`` block. Read-only by contract.
    """
    with importlib.resources.as_file(bundled_prompts_root()) as path:
        yield path


__all__ = [
    "bundled_prompt",
    "bundled_prompts_as_path",
    "bundled_prompts_root",
    "is_package_marker",
]
