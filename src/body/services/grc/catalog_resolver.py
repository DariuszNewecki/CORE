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


# ID: 738f5685-dd95-4487-ae61-05e63cc141f9
class CatalogPublicationUnknownError(RuntimeError):
    """Catalogs were found, but publication status could not be established (ADR-121 D3).

    Distinct from "no catalogs exist" (a legitimate, silent empty result):
    catalog.yaml files are present on disk, but ``inventory.yaml`` is absent or
    unreadable, so CORE cannot tell which of them are ``published``. Treating
    unknown status as published would be fail-open — the opposite of the
    honesty posture GRC gap-analysis exists to enforce — so
    ``discover_published_catalogs`` raises instead of silently degrading to
    "run everything" or silently degrading to an indistinguishable empty dict.
    """


# ID: fa063c13-756d-4a3f-9f16-958678d1beca
def resolve_catalog_root(catalog_root: Path | None = None) -> Path:
    """Resolve the GRC catalog corpus root.

    Defaults to ``PathResolver.grc_catalogs_dir``; an explicit ``catalog_root``
    (e.g. a deploy-time entitlement mount, ADR-116 D3) overrides it. PathResolver
    is in shared/ and is the governed way for body/ to resolve repo-relative paths
    without importing Settings (architecture.boundary.settings_access).
    """
    if catalog_root is not None:
        return Path(catalog_root).resolve()
    from shared.infrastructure.intent.intent_repository import get_intent_repository
    from shared.path_resolver import PathResolver

    repo_root = get_intent_repository().root.parent
    return PathResolver.from_repo(repo_root).grc_catalogs_dir


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


# ID: b530e8d0-bda8-4272-9900-2ac299cca3c5
def discover_published_catalogs(catalog_root: Path | None = None) -> dict[str, Path]:
    """Map *published*-status framework names to their ``catalog.yaml`` (ADR-121 D3).

    ``catalog_names: []`` ("run every available catalog") must not silently pull
    in a framework still being authored or awaiting source verification —
    ``discover_catalogs()`` alone doesn't know about publication status, only
    filesystem presence. This filters that result against
    ``<catalog_root>/inventory.yaml`` (ADR-116 D7's framework registry),
    keeping only entries whose ``status`` is ``published``.

    When no catalogs are discovered at all, that's returned as-is — an empty
    result, no ambiguity. But when catalogs *are* discovered and
    ``inventory.yaml`` is absent or unreadable, publication status is
    genuinely unknown, and unknown MUST NOT be treated as published: this
    raises ``CatalogPublicationUnknownError`` rather than fail-open ("run
    everything") or fail-silent (an empty dict indistinguishable from "nothing
    exists"). Callers decide how to surface that to their own audience.

    An explicit ``catalog_names`` list is the project's own opt-in and bypasses
    this gate entirely (callers apply it against ``discover_catalogs()``
    directly, never through this function).
    """
    available = discover_catalogs(catalog_root)
    if not available:
        return available

    root = resolve_catalog_root(catalog_root)
    inventory_path = root / "inventory.yaml"
    if not inventory_path.is_file():
        raise CatalogPublicationUnknownError(
            f"{len(available)} catalog(s) found at {root} "
            f"({sorted(available)}), but no inventory.yaml is present to "
            "establish publication status. Refusing to run catalogs of "
            "unknown publication status."
        )

    import yaml

    try:
        data = yaml.safe_load(inventory_path.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as e:
        raise CatalogPublicationUnknownError(
            f"{len(available)} catalog(s) found at {root} "
            f"({sorted(available)}), but {inventory_path} could not be read "
            f"to establish publication status ({e}). Refusing to run "
            "catalogs of unknown publication status."
        ) from e

    published = {
        entry["id"]
        for entry in (data.get("frameworks") or [])
        if isinstance(entry, dict) and entry.get("status") == "published"
    }
    return {name: path for name, path in available.items() if name in published}


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
