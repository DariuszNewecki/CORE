# tests/body/services/grc/test_catalog_resolver__served_tiers.py
"""#1336 — discovery serves only the licensed and public tiers, never internal/.

``grc-catalogs/internal/`` is the licence-gated audit corpus (ADR-116 D9). A
``catalog.yaml`` placed there must not be discovered: ``internal`` sorts
before ``licensed`` and ``public``, so it would otherwise win over a public
catalog of the same name.
"""

from __future__ import annotations

from pathlib import Path

from body.services.grc.catalog_resolver import discover_catalogs


def _catalog(root: Path, tier: str, framework: str) -> Path:
    path = root / tier / framework / "catalog.yaml"
    path.parent.mkdir(parents=True)
    path.write_text("framework: x\n")
    return path


def test_internal_tier_is_never_discovered(tmp_path: Path) -> None:
    public = _catalog(tmp_path, "public", "iso27001")
    _catalog(tmp_path, "internal", "iso27001")
    _catalog(tmp_path, "internal", "only_internal")

    assert discover_catalogs(tmp_path) == {"iso27001": public}


def test_licensed_overrides_public(tmp_path: Path) -> None:
    _catalog(tmp_path, "public", "soc2")
    licensed = _catalog(tmp_path, "licensed", "soc2")

    assert discover_catalogs(tmp_path) == {"soc2": licensed}
