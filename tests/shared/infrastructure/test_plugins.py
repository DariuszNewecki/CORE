"""ADR-177 D1, D2, D4, D8 (#1339 PR H): finding installed plug-ins."""

from __future__ import annotations

import importlib.metadata
import logging
from pathlib import Path

import pytest

from shared.infrastructure.plugins import fingerprint, installed_plugins
from tests.helpers.fake_plugin import ENGINE_SOURCE, install_fake_plugin


_ENGINE_FILE = {
    "engines.py": ENGINE_SOURCE.format(class_name="FakeGate", engine_id="h_fake_gate")
}


def _by_name(name: str) -> list:
    return [p for p in installed_plugins("1") if p.name == name]


def test_a_valid_plugin_is_loaded_with_its_engines_and_content(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    package_dir = install_fake_plugin(
        monkeypatch,
        tmp_path,
        dist_name="h-valid",
        package="h_valid",
        manifest=(
            '{"format_version": 1, "core_engine_api": "1", '
            '"engines": ["h_valid.engines:FakeGate"], "catalogs": "catalogs"}'
        ),
        files={**_ENGINE_FILE, "catalogs/public/x/catalog.yaml": "requirements: []\n"},
    )
    (plugin,) = _by_name("h-valid")
    assert plugin.label == "h-valid 0.1.0"
    assert [e.engine_id for e in plugin.engines] == ["h_fake_gate"]
    assert plugin.catalogs == package_dir / "catalogs"
    assert plugin.packs is None
    assert plugin.fingerprint.startswith("sha256:") and len(plugin.fingerprint) == 71
    (line,) = [r.getMessage() for r in caplog.records if "h-valid" in r.getMessage()]
    assert "h-valid 0.1.0 loaded" in line
    assert "engines [h_fake_gate]" in line
    assert "catalogs 1" in line
    assert plugin.fingerprint in line
    assert "ADR-177 D8" in line


@pytest.mark.parametrize(
    ("manifest", "why"),
    [
        ('{"format_version": 1}', "fails plugin_manifest.schema.json"),
        ('["not", "a", "mapping"]', "is not a mapping"),
        (
            '{"format_version": 1, "core_engine_api": "2"}',
            "built for core_engine_api '2'; this CORE supports '1'",
        ),
    ],
)
def test_a_broken_plugin_is_skipped_with_a_warning(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    manifest: str,
    why: str,
) -> None:
    caplog.set_level(logging.WARNING)
    package = f"h_broken_{abs(hash(manifest)) % 10**6}"
    install_fake_plugin(
        monkeypatch, tmp_path, dist_name="h-broken", package=package, manifest=manifest
    )
    assert _by_name("h-broken") == []
    (line,) = [r.getMessage() for r in caplog.records if "h-broken" in r.getMessage()]
    assert "is not loaded" in line
    assert why in line
    assert "ADR-177 D4" in line


def test_an_engine_that_fails_to_import_is_a_warning(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.WARNING)
    install_fake_plugin(
        monkeypatch,
        tmp_path,
        dist_name="h-badengine",
        package="h_badengine",
        manifest=(
            '{"format_version": 1, "core_engine_api": "1", '
            '"engines": ["h_badengine.missing:Nope"]}'
        ),
    )
    (plugin,) = _by_name("h-badengine")
    assert plugin.engines == ()
    assert any(
        "h_badengine.missing:Nope failed to import" in r.getMessage()
        and "ADR-176 D7" in r.getMessage()
        for r in caplog.records
    )


def test_plugins_load_in_name_order(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    manifest = '{"format_version": 1, "core_engine_api": "1"}'
    install_fake_plugin(
        monkeypatch,
        tmp_path / "a",
        dist_name="h-zeta",
        package="h_zeta",
        manifest=manifest,
    )
    install_fake_plugin(
        monkeypatch,
        tmp_path / "b",
        dist_name="h-alpha",
        package="h_alpha",
        manifest=manifest,
    )
    names = [p.name for p in installed_plugins("1") if p.name in {"h-zeta", "h-alpha"}]
    assert names == ["h-alpha", "h-zeta"]


def test_fingerprint_follows_file_content_and_ignores_compiled_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    package_dir = install_fake_plugin(
        monkeypatch,
        tmp_path,
        dist_name="h-print",
        package="h_print",
        manifest='{"format_version": 1, "core_engine_api": "1"}',
    )
    dist = importlib.metadata.distribution("h-print")
    first = fingerprint(dist)
    assert fingerprint(dist) == first
    (package_dir / "__pycache__").mkdir()
    (package_dir / "__pycache__" / "x.pyc").write_bytes(b"compiled")
    assert fingerprint(dist) == first
    (package_dir / "__init__.py").write_text(
        'MANIFEST = {"format_version": 1, "core_engine_api": "1"}\n# changed\n'
    )
    assert fingerprint(dist) != first
