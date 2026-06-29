# src/shared/infrastructure/intent/_floor.py
"""Bundled machinery-floor path resolver (ADR-108 D3).

Provides a single helper used by the fail-closed taxonomy and vocabulary
loaders to fall back to the packaged baseline when the consumer repo does
not supply the file at root/.intent/...
"""

from __future__ import annotations

import importlib.resources
from pathlib import Path


_INTENT_PREFIX = ".intent/"


# ID: 8b1218e0-30b9-400b-96df-dd7a450eb8a3
def resolve_floor_path(intent_rel: str) -> Path | None:
    """Return the bundled machinery-floor path for an .intent/-prefixed relative path.

    Returns None if the path does not start with '.intent/' or the file is absent
    from the bundled floor.  Callers use this as a fallback when the consumer's
    repo does not supply the file at root/.intent/...
    """
    if not intent_rel.startswith(_INTENT_PREFIX):
        return None
    floor_rel = intent_rel[len(_INTENT_PREFIX) :]
    resource = importlib.resources.files("shared._machinery_floor").joinpath(floor_rel)
    path = Path(str(resource))
    return path if path.is_file() else None
