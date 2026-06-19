# src/body/services/grc/catalog_resolver.py
"""Resolve the GRC requirements-catalog corpus (ADR-116).

The GRC catalog is licensed law-as-data that CORE *consumes*, not code it
contains. This module locates catalogs under the corpus root — a tiered,
read-only data corpus laid out as ``grc-catalogs/<tier>/<framework>/catalog.yaml``
(ADR-116 D2). Two invariants follow from the ADR and from CORE's enforced path
rules:

- **Path construction routes through PathResolver** (D4): the corpus root is
  ``PathResolver.grc_catalogs_dir``, never a bare string literal in ``src/``
  (architecture.path_access.no_hardcoded_runtime_dirs). A deploy-time
  entitlement mount may override the root via ``catalog_root``.
- **Discovery is tier-agnostic** (D2/D3): it globs across tiers, so the tier
  names (``public`` / ``licensed``) are never hardcoded here, and an absent or
  partial ``licensed/`` tier — a public clone, credential-less CI, or a partial
  entitlement — simply yields fewer catalogs, never an error.

Read-only throughout: the corpus is authored or entitled out of band, never
produced at runtime, so no filesystem write (and no FileHandler) is involved.
"""

from __future__ import annotations

from pathlib import Path

from shared.logger import getLogger


logger = getLogger(__name__)

_CATALOG_FILENAME = "catalog.yaml"


# ID: fa063c13-756d-4a3f-9f16-958678d1beca
def resolve_catalog_root(catalog_root: Path | None = None) -> Path:
    """Resolve the GRC catalog corpus root.

    Defaults to ``PathResolver.grc_catalogs_dir``; an explicit ``catalog_root``
    (e.g. a deploy-time entitlement mount, ADR-116 D3) overrides it. The
    ``settings`` import is local — mirroring the established pattern in
    ``gap_analysis_service`` — so the module carries no import-time settings
    coupling.
    """
    if catalog_root is not None:
        return Path(catalog_root).resolve()
    from shared.config import settings

    return settings.paths.grc_catalogs_dir


# ID: c2d1814a-dc77-4b3a-b066-b5f66b274e28
def discover_catalogs(catalog_root: Path | None = None) -> dict[str, Path]:
    """Map each available catalog's framework name to its ``catalog.yaml``.

    Globs ``<root>/<tier>/<framework>/catalog.yaml`` across all tiers, so the
    result is tier-agnostic (ADR-116 D2). An absent root or tier yields fewer
    entries, never an error (D3). When a framework is present in more than one
    tier the lexicographically first tier wins (``licensed`` before ``public``),
    so an entitled catalog overrides a public sample of the same name.
    """
    root = resolve_catalog_root(catalog_root)
    if not root.is_dir():
        logger.debug("GRC catalog corpus root absent: %s", root)
        return {}
    found: dict[str, Path] = {}
    for path in sorted(root.glob(f"*/*/{_CATALOG_FILENAME}")):
        framework = path.parent.name
        found.setdefault(framework, path)
    return found


# ID: dff8b271-07fe-4350-a451-93f552ad4767
def resolve_catalog_path(name: str, catalog_root: Path | None = None) -> Path:
    """Resolve one catalog's ``catalog.yaml`` by framework name.

    Raises ``FileNotFoundError`` listing what *is* available when the name is
    unknown — the same contract the previous ``catalogs/<name>.yaml`` lookup
    offered, so callers (``load_catalog``) are unchanged.
    """
    catalogs = discover_catalogs(catalog_root)
    path = catalogs.get(name)
    if path is None:
        raise FileNotFoundError(
            f"Unknown GRC catalog {name!r}. Available: {sorted(catalogs)}"
        )
    return path
