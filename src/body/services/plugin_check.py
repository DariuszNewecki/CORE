# src/body/services/plugin_check.py

"""Check an installed plug-in against the contract (ADR-177 D7).

``check_installed_plugin`` gathers everything CORE would say about one
installed plug-in into one report, meant to be kept as validation evidence:

- the manifest and engine imports (ADR-177 D4, ADR-176 D7);
- each engine class through the public conformance checks
  (``mind.engine_api.conformance``: ADR-176 D2, D5(b), D6);
- each engine built with the injected services and run once on a minimal
  input: ``verify`` returns an ``EngineResult``, ``evaluate_record`` a
  ``RulePart`` (ADR-177 D7);
- id collisions with CORE or other plug-ins: engines, catalogs, packs
  (ADR-177 D5);
- each catalog through the ADR-174 checks, each pack through the pack loader
  (ADR-149).

Read-only: the engine run reads the plug-in's own manifest module as its
sample file; nothing is written or stored.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mind.engine_api import EngineResult, RulePart
from mind.engine_api.conformance import check_engine, engine_id_collisions
from shared.infrastructure.plugins import (
    InstalledPlugin,
    inspect_plugin,
    installed_plugins,
)


@dataclass(frozen=True)
# ID: 3e3b1bc5-cd43-4bd4-a2ff-61de83d9cb63
class PluginProblem:
    """One problem: the rule it breaks, what it concerns, and what is wrong."""

    rule: str
    subject: str
    message: str


@dataclass
# ID: 03ec57d0-50e5-4e1f-9c1e-35e33805d691
class PluginCheckReport:
    """The result of checking one installed plug-in. ``conforms`` is True
    when it loads and no problem was found."""

    name: str
    version: str
    loaded: bool
    fingerprint: str = ""
    core_engine_api: str = ""
    engines: list[str] = field(default_factory=list)
    catalogs: list[str] = field(default_factory=list)
    packs: list[str] = field(default_factory=list)
    problems: list[PluginProblem] = field(default_factory=list)

    @property
    # ID: 2351cf6c-8f2d-45d0-81da-01ed39fe7fcf
    def conforms(self) -> bool:
        """True when the plug-in loads and has no problem."""
        return self.loaded and not self.problems

    # ID: 27c708a5-431e-448c-b048-3fc06441c204
    def to_dict(self) -> dict[str, Any]:
        """The report as plain data (``plugin-check/1``)."""
        return {
            "format": "plugin-check/1",
            "plugin": self.name,
            "version": self.version,
            "loaded": self.loaded,
            "conforms": self.conforms,
            "fingerprint": self.fingerprint,
            "core_engine_api": self.core_engine_api,
            "engines": self.engines,
            "catalogs": self.catalogs,
            "packs": self.packs,
            "problems": [
                {"rule": p.rule, "subject": p.subject, "message": p.message}
                for p in self.problems
            ],
        }


# ID: 23f1b2e2-57b0-47a0-8ed2-720b72ec1b2b
def list_installed_plugins() -> list[InstalledPlugin]:
    """The installed plug-ins that load, in name order (ADR-177 D2)."""
    return installed_plugins(log=False)


# ID: f423d895-d584-4cf1-8bdb-35406590c015
def plugin_summaries() -> list[dict[str, Any]]:
    """Name, version and fingerprint of each loaded plug-in, for an audit
    result (ADR-177 D8)."""
    return [
        {"name": p.name, "version": p.version, "fingerprint": p.fingerprint}
        for p in list_installed_plugins()
    ]


# ID: bb8d2271-af5a-41cf-9723-8123a534468b
async def check_installed_plugin(name: str) -> PluginCheckReport | None:
    """Every contract problem of the installed plug-in ``name``, or None when
    no installed package declares a plug-in under that name."""
    inspection = inspect_plugin(name)
    if inspection is None:
        return None
    report = PluginCheckReport(
        name=inspection.name, version=inspection.version, loaded=False
    )
    plugin = inspection.plugin
    rule = "ADR-177 D4" if plugin is None else "ADR-176 D7"
    report.problems += [
        PluginProblem(rule, "manifest" if plugin is None else "engines", m)
        for m in inspection.problems
    ]
    if plugin is None:
        return report
    report.loaded = True
    report.fingerprint = plugin.fingerprint
    report.core_engine_api = plugin.core_engine_api
    report.engines = [getattr(e, "engine_id", e.__name__) for e in plugin.engines]
    for engine_cls in plugin.engines:
        subject = getattr(engine_cls, "engine_id", engine_cls.__name__)
        report.problems += [
            PluginProblem(p.rule, subject, p.message) for p in check_engine(engine_cls)
        ]
        report.problems += await _smoke(
            engine_cls, subject, plugin.root / "__init__.py"
        )
    report.problems += _collisions(plugin)
    report.catalogs, catalog_problems = _check_catalogs(plugin)
    report.problems += catalog_problems
    report.packs, pack_problems = _check_packs(plugin)
    report.problems += pack_problems
    return report


async def _smoke(engine_cls: type, subject: str, sample: Path) -> list[PluginProblem]:
    """Build the engine as the registry does and run it once on ``sample``,
    an existing file it only reads (ADR-177 D7)."""
    from shared.path_resolver import PathResolver

    services: dict[str, Any] = {
        "path_resolver": PathResolver.from_repo(_repo_root()),
        "llm_client": None,
        "embedding_client": None,
    }
    try:
        params = inspect.signature(engine_cls.__init__).parameters  # type: ignore[misc]
        engine = engine_cls(**{k: v for k, v in services.items() if k in params})
    except Exception as exc:
        return [PluginProblem("ADR-177 D7", subject, f"cannot be built: {exc}")]
    problems: list[PluginProblem] = []
    try:
        result = await engine.verify(sample, {})
        if not isinstance(result, EngineResult):
            problems.append(
                PluginProblem(
                    "ADR-177 D7",
                    subject,
                    f"verify returned {type(result).__name__}, not EngineResult",
                )
            )
    except Exception as exc:
        problems.append(
            PluginProblem(
                "ADR-177 D7", subject, f"verify raised on a minimal input: {exc}"
            )
        )
    if getattr(engine_cls, "supports_records", False):
        try:
            part = await engine.evaluate_record({}, f"{subject}.conformance", {})
            if not isinstance(part, RulePart):
                problems.append(
                    PluginProblem(
                        "ADR-177 D7",
                        subject,
                        f"evaluate_record returned {type(part).__name__}, not RulePart",
                    )
                )
        except Exception as exc:
            problems.append(
                PluginProblem(
                    "ADR-177 D7",
                    subject,
                    f"evaluate_record raised on an empty record: {exc}",
                )
            )
    return problems


def _collisions(plugin: InstalledPlugin) -> list[PluginProblem]:
    from body.services.grc.catalog_resolver import (
        CatalogIdCollisionError,
        discover_catalogs,
    )
    from shared.infrastructure.intent.pack_loader import (
        PackIdCollisionError,
        list_pack_ids_from_sources,
    )

    problems = [
        PluginProblem("ADR-177 D5", "engines", message)
        for message in engine_id_collisions()
    ]
    try:
        discover_catalogs()
    except CatalogIdCollisionError as exc:
        problems.append(PluginProblem("ADR-177 D5", "catalogs", str(exc)))
    try:
        list_pack_ids_from_sources(_repo_root())
    except PackIdCollisionError as exc:
        problems.append(PluginProblem("ADR-177 D5", "packs", str(exc)))
    return problems


def _check_catalogs(plugin: InstalledPlugin) -> tuple[list[str], list[PluginProblem]]:
    from body.services.grc.catalog_contract import check_catalog, check_catalog_root
    from body.services.grc.catalog_resolver import _discover_in

    if plugin.catalogs is None:
        return [], []
    found = _discover_in(plugin.catalogs)
    warnings = check_catalog_root(plugin.catalogs)
    for path in found.values():
        warnings += check_catalog(path)
    problems = [PluginProblem(w.rule_id, w.catalog, w.message) for w in warnings]
    return sorted(found), problems


def _check_packs(plugin: InstalledPlugin) -> tuple[list[str], list[PluginProblem]]:
    from shared.infrastructure.intent.pack_loader import PackLoader

    if plugin.packs is None:
        return [], []
    loader = PackLoader(plugin.packs)
    ids = loader.list_pack_ids()
    problems: list[PluginProblem] = []
    for pack_id in ids:
        try:
            loader.load_pack(pack_id)
        except Exception as exc:
            problems.append(
                PluginProblem("ADR-149", pack_id, f"pack cannot be loaded: {exc}")
            )
    files = sorted(plugin.packs.glob("*.yaml"))
    if len(files) > len(ids):
        problems.append(
            PluginProblem(
                "ADR-149",
                "packs",
                f"{len(files) - len(ids)} pack file(s) declare no readable id",
            )
        )
    return sorted(ids), problems


def _repo_root() -> Path:
    from shared.infrastructure.intent.intent_repository import get_intent_repository

    return get_intent_repository().root.parent


__all__ = [
    "PluginCheckReport",
    "PluginProblem",
    "check_installed_plugin",
    "list_installed_plugins",
    "plugin_summaries",
]
