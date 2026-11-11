"""The catalog contract in warn mode (ADR-174, #1338).

Per rule one compliant case and one case that draws the warning; the bundled
catalogs draw none; a warned catalog still loads.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from body.services.grc import catalog_contract
from body.services.grc.catalog_contract import (
    CatalogContractWarning,
    check_catalog,
    check_catalog_root,
    log_warnings,
)
from body.services.grc.gap_analysis_service import load_catalog
from mind.logic.engines.registry import EngineRegistry


_REPO = Path(__file__).resolve().parents[4]

_CATALOG = """\
format_version: 1
catalog:
  id: {fw}
  title: "Sample framework"
requirements:
  - id: {fw}.doc_finalized
    engine: {engine}
    statement: "Documents MUST be finalized."
    params:
      forbidden_patterns: ['\\bTODO\\b']
"""
_PROVENANCE = """\
format_version: 1
framework: "Sample framework"
tier: public
catalog: catalog.yaml
source:
  publisher: "Sample publisher"
"""
_INVENTORY = """\
format_version: 1
frameworks:
  - id: sample
    tier: public
    status: published
"""


def _tree(
    root: Path,
    *,
    catalog: str | None = None,
    provenance: str | None = _PROVENANCE,
    inventory: str = _INVENTORY,
    engine: str = "regex_gate",
) -> Path:
    fw = root / "public" / "sample"
    fw.mkdir(parents=True)
    path = fw / "catalog.yaml"
    path.write_text(catalog or _CATALOG.format(fw="sample", engine=engine))
    if provenance is not None:
        (fw / "provenance.yaml").write_text(provenance)
    (root / "inventory.yaml").write_text(inventory)
    return path


def _rules(warnings: list[CatalogContractWarning]) -> list[str]:
    return [w.rule_id for w in warnings]


# ID: 1f6a3c8e-2b4d-4e9a-a7c5-8d0e3b6f1a42
def test_compliant_tree_has_no_warnings(tmp_path: Path) -> None:
    path = _tree(tmp_path)
    assert check_catalog(path) == []
    assert check_catalog_root(tmp_path) == []


# ID: 7b2e9d4a-6c1f-4a3e-8b5d-0f9c2e7a4d13
@pytest.mark.parametrize("which", ["catalog", "provenance", "inventory"])
def test_d1_missing_format_version_warns(tmp_path: Path, which: str) -> None:
    def strip(text: str) -> str:
        return text.replace("format_version: 1\n", "")

    catalog = _CATALOG.format(fw="sample", engine="regex_gate")
    path = _tree(
        tmp_path,
        catalog=strip(catalog) if which == "catalog" else catalog,
        provenance=strip(_PROVENANCE) if which == "provenance" else _PROVENANCE,
        inventory=strip(_INVENTORY) if which == "inventory" else _INVENTORY,
    )
    warnings = check_catalog(path) + check_catalog_root(tmp_path)

    assert _rules(warnings) == ["ADR-174 D1"]
    text = str(warnings[0])
    assert "has no format_version" in text
    assert "becomes a refusal in CORE 4.0" in text
    assert text.startswith(
        "catalog root " if which == "inventory" else "catalog sample:"
    )


# ID: 3d8c1a6e-9f2b-4e7d-b4a1-6e0c9d3f8b27
def test_d3_schema_failure_warns(tmp_path: Path) -> None:
    broken = """\
format_version: 1
catalog:
  id: sample
requirements:
  - id: sample.no_engine
    statement: "No engine named."
"""
    warnings = check_catalog(_tree(tmp_path, catalog=broken))

    assert _rules(warnings) == ["ADR-174 D3"]
    assert "catalog.schema.json at requirements/0" in warnings[0].message
    assert "'engine' is a required property" in warnings[0].message


# ID: 5a9e2c7b-1d4f-4b8a-9e3c-7f1b0d4a6e58
def test_d3_wrong_format_version_value_warns(tmp_path: Path) -> None:
    catalog = _CATALOG.format(fw="sample", engine="regex_gate").replace(
        "format_version: 1", "format_version: 2"
    )
    assert _rules(check_catalog(_tree(tmp_path, catalog=catalog))) == ["ADR-174 D3"]


# ID: 9c4f1e7a-3b6d-4a2e-8d5b-2a7e0c9f3b61
def test_d4_missing_provenance_warns(tmp_path: Path) -> None:
    warnings = check_catalog(_tree(tmp_path, provenance=None))

    assert _rules(warnings) == ["ADR-174 D4"]
    assert "has no provenance.yaml" in warnings[0].message


# ID: 2e7b5d9c-4a1f-4c6e-b3d8-9f0a6e2c7d14
def test_d7_catalog_under_internal_warns(tmp_path: Path) -> None:
    _tree(tmp_path)
    assert check_catalog_root(tmp_path) == []

    internal = tmp_path / "internal" / "sample"
    internal.mkdir(parents=True)
    (internal / "catalog.yaml").write_text("format_version: 1\n")
    warnings = check_catalog_root(tmp_path)

    assert _rules(warnings) == ["ADR-174 D7"]
    assert warnings[0].catalog == "sample"
    assert "is ignored" in warnings[0].message


# ID: 6d1a8f3e-7c2b-4e9d-a5f1-3b8e0d6c2a97
def test_d8_unknown_engine_warns(tmp_path: Path) -> None:
    warnings = check_catalog(_tree(tmp_path, engine="no_such_engine"))

    assert _rules(warnings) == ["ADR-174 D8"]
    assert "unknown engine 'no_such_engine'" in warnings[0].message


# ID: 8b3e6a1d-5f9c-4d2a-b7e4-1c0f8a3d6e25
def test_d8_passive_alias_is_a_known_engine(tmp_path: Path) -> None:
    assert "advisory" in EngineRegistry.known_engine_ids()
    assert "regex_gate" in EngineRegistry.known_engine_ids()
    assert check_catalog(_tree(tmp_path, engine="advisory")) == []


# ID: 4f8d2b6e-9a3c-4e1f-8c7a-5d0b2e9f4a36
@pytest.mark.parametrize("root", ["grc-catalogs", "src/shared/_grc_catalogs"])
def test_bundled_catalogs_have_no_warnings(root: str) -> None:
    base = _REPO / root
    catalogs = sorted(base.glob("public/*/catalog.yaml"))
    assert len(catalogs) == 4
    warnings = check_catalog_root(base)
    for path in catalogs:
        warnings += check_catalog(path)
    assert [str(w) for w in warnings] == []


# ID: 0a7c3e9f-2d5b-4f8e-a6c1-9e3b7d0f5c48
def test_warned_catalog_still_loads_and_logs_once(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(catalog_contract, "_logged", set())
    catalog = _CATALOG.format(fw="sample", engine="regex_gate").replace(
        "format_version: 1\n", ""
    )
    _tree(tmp_path, catalog=catalog, provenance=None)

    with caplog.at_level(logging.WARNING):
        rules = load_catalog("sample", catalog_root=tmp_path)
        load_catalog("sample", catalog_root=tmp_path)

    assert [r.rule_id for r in rules] == ["sample.doc_finalized"]
    lines = [
        r.getMessage() for r in caplog.records if "Catalog contract" in r.getMessage()
    ]
    assert lines == [
        "Catalog contract: catalog sample: ADR-174 D1 catalog.yaml has no "
        "format_version; this becomes a refusal in CORE 4.0",
        "Catalog contract: catalog sample: ADR-174 D4 has no provenance.yaml "
        "beside catalog.yaml; this becomes a refusal in CORE 4.0",
    ]


# ID: c5e1b8a4-6f3d-4a9e-b2c7-8d4f0a1e6b93
def test_log_warnings_dedupes(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(catalog_contract, "_logged", set())
    w = CatalogContractWarning("sample", "ADR-174 D4", "has no provenance.yaml")
    with caplog.at_level(logging.WARNING):
        log_warnings([w, w])
        log_warnings([w])
    assert sum("Catalog contract" in r.getMessage() for r in caplog.records) == 1
