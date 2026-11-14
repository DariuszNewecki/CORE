"""ADR-177 D3, D5 (#1339 PR I): plug-in catalog roots in catalog loading."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from body.services.grc import catalog_resolver
from body.services.grc.catalog_resolver import (
    CatalogIdCollisionError,
    CatalogPublicationUnknownError,
    discover_catalogs,
    discover_published_catalogs,
)
from body.services.grc.gap_analysis_service import load_catalog
from tests.helpers.fake_plugin import install_fake_plugin


_CATALOG = """\
format_version: 1
framework: {name}
catalog_version: "1.0"
requirements:
  - id: {name}.r1
    statement: "A document exists."
    engine: attestation_gate
    params: {{}}
"""
_INVENTORY = """\
frameworks:
  - id: {name}
    status: published
"""


def _base(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *names: str) -> Path:
    base = tmp_path / "base"
    for name in names:
        (base / "public" / name).mkdir(parents=True)
        (base / "public" / name / "catalog.yaml").write_text(_CATALOG.format(name=name))
    (base).mkdir(exist_ok=True)
    (base / "inventory.yaml").write_text(
        "frameworks:\n"
        + "".join(f"  - id: {n}\n    status: published\n" for n in names)
    )
    monkeypatch.setattr(
        catalog_resolver,
        "resolve_catalog_root",
        lambda catalog_root=None: Path(catalog_root) if catalog_root else base,
    )
    return base


def _plugin(
    monkeypatch: pytest.MonkeyPatch,
    site: Path,
    dist: str,
    name: str,
    *,
    inventory: bool = True,
) -> Path:
    package = dist.replace("-", "_")
    files = {f"catalogs/public/{name}/catalog.yaml": _CATALOG.format(name=name)}
    if inventory:
        files["catalogs/inventory.yaml"] = _INVENTORY.format(name=name)
    package_dir = install_fake_plugin(
        monkeypatch,
        site,
        dist_name=dist,
        package=package,
        manifest='{"format_version": 1, "core_engine_api": "1", "catalogs": "catalogs"}',
        files=files,
    )
    return package_dir / "catalogs" / "public" / name / "catalog.yaml"


def test_plugin_catalogs_join_the_default_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    base = _base(tmp_path, monkeypatch, "core_cat")
    plugin_path = _plugin(monkeypatch, tmp_path / "site", "ic-one", "plugin_cat")
    assert discover_catalogs() == {
        "core_cat": base / "public" / "core_cat" / "catalog.yaml",
        "plugin_cat": plugin_path,
    }
    assert set(discover_published_catalogs()) == {"core_cat", "plugin_cat"}


def test_an_explicit_root_reads_that_root_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    base = _base(tmp_path, monkeypatch, "core_cat")
    _plugin(monkeypatch, tmp_path / "site", "ic-explicit", "plugin_cat")
    assert set(discover_catalogs(base)) == {"core_cat"}


def test_a_plugin_catalog_with_a_core_name_refuses(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _base(tmp_path, monkeypatch, "shared_cat")
    _plugin(monkeypatch, tmp_path / "site", "ic-clash", "shared_cat")
    with pytest.raises(CatalogIdCollisionError) as exc:
        discover_catalogs()
    message = str(exc.value)
    assert "'shared_cat'" in message
    assert "catalog root" in message
    assert "plug-in ic-clash 0.1.0" in message
    assert "ADR-177 D5" in message
    with pytest.raises(CatalogIdCollisionError):
        discover_published_catalogs()


def test_two_plugins_with_one_catalog_name_refuse(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _base(tmp_path, monkeypatch)
    _plugin(monkeypatch, tmp_path / "a", "ic-first", "twin_cat")
    _plugin(monkeypatch, tmp_path / "b", "ic-second", "twin_cat")
    with pytest.raises(CatalogIdCollisionError) as exc:
        discover_catalogs()
    assert "plug-in ic-first 0.1.0" in str(exc.value)
    assert "plug-in ic-second 0.1.0" in str(exc.value)


def test_a_plugin_root_without_inventory_is_unknown_publication(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _base(tmp_path, monkeypatch)
    _plugin(monkeypatch, tmp_path / "site", "ic-noinv", "plugin_cat", inventory=False)
    with pytest.raises(CatalogPublicationUnknownError):
        discover_published_catalogs()


def test_a_plugin_catalog_goes_through_the_catalog_contract(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.WARNING)
    _base(tmp_path, monkeypatch)
    _plugin(monkeypatch, tmp_path / "site", "ic-contract", "contract_cat")
    rules = load_catalog("contract_cat")
    assert [r.rule_id for r in rules] == ["contract_cat.r1"]
    # No provenance.yaml beside the plug-in's catalog: the ADR-174 D4 warning.
    assert any(
        "contract_cat" in r.getMessage() and "ADR-174 D4" in r.getMessage()
        for r in caplog.records
    )
