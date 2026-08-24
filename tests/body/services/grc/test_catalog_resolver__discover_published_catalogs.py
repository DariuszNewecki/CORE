# tests/body/services/grc/test_catalog_resolver__discover_published_catalogs.py
"""ADR-121 D3 — published-only catalog discovery, fail-closed on unknown status.

``catalog_names: []`` ("run every available catalog") must not silently pull
in a framework still ``authored``/``planned`` per ``inventory.yaml`` — only
``status: published`` entries qualify. When catalogs exist but publication
status can't be established (no/unreadable inventory.yaml), that is a fail
condition — CatalogPublicationUnknownError — never "run everything" and never
a silent empty result indistinguishable from "nothing exists".
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from body.services.grc.catalog_resolver import (
    CatalogPublicationUnknownError,
    discover_published_catalogs,
)


# ID: 6b6cb9c1-3f2f-4c46-9df1-4d3d0d7d0e2b
def _make_catalog_root(tmp_path: Path, frameworks: dict[str, str]) -> Path:
    """Build a catalog_root with one catalog.yaml per framework and an inventory.yaml."""
    root = tmp_path / "catalogs"
    entries = []
    for name, status in frameworks.items():
        fw_dir = root / "public" / name
        fw_dir.mkdir(parents=True)
        (fw_dir / "catalog.yaml").write_text("catalog: {id: " + name + "}\n")
        entries.append({"id": name, "status": status})
    root.mkdir(exist_ok=True)
    (root / "inventory.yaml").write_text(
        yaml.dump({"frameworks": entries}), encoding="utf-8"
    )
    return root


def test_discover_published_catalogs_filters_out_unpublished(
    tmp_path: Path,
) -> None:
    """catalog_names empty + inventory present → published only."""
    root = _make_catalog_root(
        tmp_path,
        {"ready": "published", "draft": "authored", "future": "planned"},
    )

    found = discover_published_catalogs(root)

    assert set(found.keys()) == {"ready"}


def test_discover_published_catalogs_no_inventory_raises(
    tmp_path: Path,
) -> None:
    """catalog_names empty + inventory absent → fail closed, not fail-open."""
    root = tmp_path / "catalogs"
    fw_dir = root / "public" / "contract_review"
    fw_dir.mkdir(parents=True)
    (fw_dir / "catalog.yaml").write_text("catalog: {id: contract_review}\n")

    with pytest.raises(CatalogPublicationUnknownError, match="contract_review"):
        discover_published_catalogs(root)


def test_discover_published_catalogs_unreadable_inventory_raises(
    tmp_path: Path,
) -> None:
    """catalog_names empty + inventory present but unparseable → fail closed."""
    root = tmp_path / "catalogs"
    fw_dir = root / "public" / "nist_800_171"
    fw_dir.mkdir(parents=True)
    (fw_dir / "catalog.yaml").write_text("catalog: {id: nist_800_171}\n")
    (root / "inventory.yaml").write_text(": not valid yaml: [", encoding="utf-8")

    with pytest.raises(CatalogPublicationUnknownError, match="nist_800_171"):
        discover_published_catalogs(root)


def test_discover_published_catalogs_empty_root_returns_empty(
    tmp_path: Path,
) -> None:
    """No catalogs discovered at all → legitimately empty, no ambiguity, no raise."""
    root = tmp_path / "does_not_exist"

    found = discover_published_catalogs(root)

    assert found == {}
