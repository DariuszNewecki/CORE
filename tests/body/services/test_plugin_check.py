"""ADR-177 D5, D7, D8 (#1339 PR J): checking an installed plug-in."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

import mind.logic.engines.registry as registry_module
from body.services.plugin_check import (
    _smoke,
    check_installed_plugin,
    plugin_summaries,
)
from mind.logic.engines.registry import EngineRegistry
from shared.path_resolver import PathResolver
from tests.helpers.fake_plugin import ENGINE_SOURCE, install_fake_plugin


_REPO_ROOT = Path(__file__).resolve().parents[3]
_EXAMPLE = _REPO_ROOT / "examples" / "plugin-example" / "src" / "core_plugin_example"


@pytest.fixture(autouse=True)
def _restore_registry() -> Iterator[None]:
    saved = (
        dict(EngineRegistry._instances),
        dict(EngineRegistry._engine_classes),
        dict(EngineRegistry._engine_sources),
        list(EngineRegistry._plugins),
        EngineRegistry._path_resolver,
        EngineRegistry._discovered,
        set(registry_module.PASSIVE_ALIASES),
    )
    yield
    EngineRegistry._instances.clear()
    EngineRegistry._instances.update(saved[0])
    EngineRegistry._engine_classes.clear()
    EngineRegistry._engine_classes.update(saved[1])
    EngineRegistry._engine_sources.clear()
    EngineRegistry._engine_sources.update(saved[2])
    EngineRegistry._plugins = saved[3]
    EngineRegistry._path_resolver = saved[4]
    EngineRegistry._discovered = saved[5]
    registry_module.PASSIVE_ALIASES = saved[6]


def _install_example(monkeypatch: pytest.MonkeyPatch, site: Path) -> None:
    """The public example plug-in, installed as a package would be."""
    files = {
        str(p.relative_to(_EXAMPLE)): p.read_text(encoding="utf-8")
        for p in _EXAMPLE.rglob("*")
        if p.is_file() and p.name != "__init__.py" and "__pycache__" not in p.parts
    }
    manifest = (_EXAMPLE / "__init__.py").read_text(encoding="utf-8")
    manifest_literal = manifest[manifest.index("MANIFEST = ") + len("MANIFEST = ") :]
    install_fake_plugin(
        monkeypatch,
        site,
        dist_name="core-plugin-example",
        package="core_plugin_example",
        manifest=manifest_literal.strip(),
        files=files,
    )


async def test_the_example_plugin_conforms(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _install_example(monkeypatch, tmp_path)
    report = await check_installed_plugin("core-plugin-example")
    assert report is not None
    assert report.problems == []
    assert report.conforms
    assert report.engines == ["example_no_todo_gate"]
    assert report.catalogs == ["example_no_todo"]
    data = report.to_dict()
    assert data["format"] == "plugin-check/1"
    assert data["conforms"] is True
    assert data["fingerprint"].startswith("sha256:")


async def test_an_unknown_plugin_gives_none() -> None:
    assert await check_installed_plugin("no-such-plugin-installed") is None


async def test_a_bad_manifest_is_reported_and_not_loaded(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    install_fake_plugin(
        monkeypatch,
        tmp_path,
        dist_name="j-badmanifest",
        package="j_badmanifest",
        manifest='{"format_version": 1}',
    )
    report = await check_installed_plugin("j-badmanifest")
    assert report is not None and not report.loaded and not report.conforms
    assert [p.rule for p in report.problems] == ["ADR-177 D4"]
    assert "plugin_manifest.schema.json" in report.problems[0].message


_SYNC_AND_CRASHING = """
from pathlib import Path
from typing import Any

from mind.engine_api import BaseEngine, EngineResult


class SyncGate(BaseEngine):
    engine_id = "j_sync_gate"

    def verify(self, file_path: Path, params: dict[str, Any]) -> EngineResult:
        return EngineResult(ok=True, message="ok", violations=[], engine_id=self.engine_id)


class CrashGate(BaseEngine):
    engine_id = "j_crash_gate"

    async def verify(self, file_path: Path, params: dict[str, Any]) -> EngineResult:
        raise RuntimeError("boom")
"""


async def test_engine_problems_are_reported(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    install_fake_plugin(
        monkeypatch,
        tmp_path,
        dist_name="j-engines",
        package="j_engines",
        manifest=(
            '{"format_version": 1, "core_engine_api": "1", "engines": '
            '["j_engines.engines:SyncGate", "j_engines.engines:CrashGate", '
            '"j_engines.engines:Missing"]}'
        ),
        files={"engines.py": _SYNC_AND_CRASHING},
    )
    report = await check_installed_plugin("j-engines")
    assert report is not None and report.loaded and not report.conforms
    found = {(p.rule, p.subject) for p in report.problems}
    assert ("ADR-176 D7", "engines") in found  # Missing failed to import
    assert ("ADR-176 D2", "j_sync_gate") in found  # verify is not async
    assert ("ADR-177 D7", "j_crash_gate") in found  # raised on a minimal input


async def test_a_collision_with_a_builtin_is_a_problem_not_a_crash(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    install_fake_plugin(
        monkeypatch,
        tmp_path,
        dist_name="j-clash",
        package="j_clash",
        manifest=(
            '{"format_version": 1, "core_engine_api": "1", '
            '"engines": ["j_clash.engines:ClashGate"]}'
        ),
        files={
            "engines.py": ENGINE_SOURCE.format(
                class_name="ClashGate", engine_id="glob_gate"
            )
        },
    )
    report = await check_installed_plugin("j-clash")
    assert report is not None
    assert any(
        p.rule == "ADR-177 D5" and "glob_gate" in p.message for p in report.problems
    )


async def test_catalog_contract_problems_are_reported(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    install_fake_plugin(
        monkeypatch,
        tmp_path,
        dist_name="j-catalog",
        package="j_catalog",
        manifest='{"format_version": 1, "core_engine_api": "1", "catalogs": "catalogs"}',
        files={
            "catalogs/inventory.yaml": "format_version: 1\nframeworks: []\n",
            "catalogs/public/j_cat/catalog.yaml": (
                "format_version: 1\ncatalog: {id: j_cat}\nrequirements: []\n"
            ),
        },
    )
    report = await check_installed_plugin("j-catalog")
    assert report is not None and report.catalogs == ["j_cat"]
    assert ("ADR-174 D4", "j_cat") in {(p.rule, p.subject) for p in report.problems}


@pytest.mark.parametrize(
    "engine_id",
    sorted(
        _n
        for _n in [
            "artifact_gate",
            "ast_gate",
            "attestation_gate",
            "cli_gate",
            "contracts_gate",
            "exclusion_gate",
            "glob_gate",
            "grc_judge",
            "knowledge_gate",
            "llm_gate",
            "llm_gate_stub",
            "passive_gate",
            "publication_gate",
            "reference_gate",
            "regex_gate",
            "schema_gate",
            "taxonomy_gate",
            "workflow_gate",
        ]
    ),
)
async def test_every_builtin_engine_passes_the_run_check(engine_id: str) -> None:
    EngineRegistry.initialize(PathResolver.from_repo(_REPO_ROOT))
    sample = _REPO_ROOT / "README.md"
    assert (
        await _smoke(EngineRegistry._engine_classes[engine_id], engine_id, sample) == []
    )


def test_plugin_summaries_name_version_and_fingerprint(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _install_example(monkeypatch, tmp_path)
    (row,) = [r for r in plugin_summaries() if r["name"] == "core-plugin-example"]
    assert row["version"] == "0.1.0"
    assert row["fingerprint"].startswith("sha256:")
