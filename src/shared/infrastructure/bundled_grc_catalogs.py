# src/shared/infrastructure/bundled_grc_catalogs.py

"""Bundled public GRC catalog corpus.

ADR-116 D6 (amended 2026-10-03): the public GRC catalogs are part of the open
product and ship in the ``core-runtime`` wheel; licensed and internal catalogs
never do. The wheel carries them as package data under
``shared._grc_catalogs`` -- a mirror of the repository's ``grc-catalogs/``
public tier and its ``inventory.yaml``. This module is the only place that
names that package.

Precedence is **repository first, bundle second**, as for packs (ADR-149) and
prompts (#909): a repository with a ``grc-catalogs/`` corpus (a CORE source
checkout, or a deployment with an entitlement mount there) reads its own; a
``pip install core-runtime`` user reads the bundle. The bundle is read-only.

Pure functions; no settings import, so this is usable before bootstrap.
"""

from __future__ import annotations

import importlib.resources
from pathlib import Path


_GRC_PACKAGE = "shared._grc_catalogs"


# ID: 10aaff9d-fe00-4edd-bf8f-f49aa06f59e6
def bundled_grc_catalogs_dir() -> Path | None:
    """The bundled public corpus as a directory, or None when unavailable.

    An installed wheel resolves to a real directory. A zip-imported install
    has no directory to hand out; callers then see no bundled corpus, which
    ADR-116 D3 treats as an absent tier, not an error.
    """
    root = importlib.resources.files(_GRC_PACKAGE)
    return root if isinstance(root, Path) and root.is_dir() else None


__all__ = ["bundled_grc_catalogs_dir"]
