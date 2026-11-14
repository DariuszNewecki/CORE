# src/shared/infrastructure/plugins.py

"""Installed plug-ins (ADR-177).

A plug-in is an installed package with an entry point in the group
``core.plugins`` that names its manifest (D1). This module finds every
installed plug-in (D2), checks its manifest against
``plugin_manifest.schema.json`` and its ``core_engine_api`` (D4), imports the
engine classes it names, and computes its fingerprint (D8). It registers
nothing: the engine registry takes the classes in through its single
registration point (ADR-176 D4).

A plug-in that fails a check is skipped with a warning naming it and
"ADR-177 D4"; an engine that fails to import is a warning (ADR-176 D7). Neither
stops CORE, and rules that name a skipped engine give the engine-missing
finding.

Installing a package is the act of trusting it: loading runs its code.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import importlib.resources
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from shared.logger import getLogger


logger = getLogger(__name__)

# ADR-176 D3: the major version of the engine interface this CORE implements.
# A breaking change to the interface is version "2", announced in the CHANGELOG.
# Defined here, in shared, so content loading can check plug-ins without
# importing mind; mind.logic.engines.base and mind.engine_api re-export it.
CORE_ENGINE_API: Final[str] = "1"

ENTRY_POINT_GROUP = "core.plugins"
_SCHEMA_FILENAME = "plugin_manifest.schema.json"
_FINGERPRINT_SKIP_SUFFIXES = (".pyc", ".pyo")
_FINGERPRINT_SKIP_NAMES = frozenset(
    {"RECORD", "INSTALLER", "REQUESTED", "direct_url.json"}
)


@dataclass(frozen=True)
# ID: 191a44e8-979e-4ef8-bf56-05cb5665469d
class InstalledPlugin:
    """One loaded plug-in: who it is, what it brings, and its fingerprint."""

    name: str
    version: str
    core_engine_api: str
    root: Path
    engines: tuple[type, ...]
    catalogs: Path | None
    packs: Path | None
    fingerprint: str

    @property
    # ID: 1410e1fe-a4b6-43b5-9b93-1c6ffee6819d
    def label(self) -> str:
        """``name version``, as the log and the refusals name the plug-in."""
        return f"{self.name} {self.version}"


# ID: 635b1349-17a9-48f8-b26d-cd3e224a978b
def installed_plugins(
    core_engine_api: str = CORE_ENGINE_API, *, log: bool = True
) -> list[InstalledPlugin]:
    """Every installed plug-in that passes its checks, in name order (D2).

    A plug-in built for another ``core_engine_api`` (default: this CORE's
    ``CORE_ENGINE_API``) is skipped (D4). ``log`` writes the D8 line per plug-in and the D4
    warnings; the engine registry logs, content lookups do not repeat it.
    """
    entry_points = sorted(
        importlib.metadata.entry_points(group=ENTRY_POINT_GROUP),
        key=lambda ep: (_dist_name(ep), ep.name),
    )
    plugins: list[InstalledPlugin] = []
    for entry_point in entry_points:
        plugin = _load(entry_point, core_engine_api, log=log)
        if plugin is not None:
            plugins.append(plugin)
            if log:
                _log_loaded(plugin)
    return plugins


@dataclass(frozen=True)
# ID: 4a3628df-77a4-4a3e-99b3-e46fc38f60c9
class PluginInspection:
    """What loading one installed plug-in found: the plug-in when it loads,
    and every reason it would be skipped or lose an engine."""

    name: str
    version: str
    plugin: InstalledPlugin | None
    problems: tuple[str, ...]


# ID: 17d0e20f-6e04-4887-99eb-9af20882d77b
def inspect_plugin(
    name: str, core_engine_api: str = CORE_ENGINE_API
) -> PluginInspection | None:
    """Load the installed plug-in ``name`` without logging and return what
    was found, or None when no installed package declares a ``core.plugins``
    entry point under that name."""
    for entry_point in importlib.metadata.entry_points(group=ENTRY_POINT_GROUP):
        if _dist_name(entry_point) != name:
            continue
        dist = entry_point.dist
        problems: list[str] = []
        plugin = _load(entry_point, core_engine_api, log=False, problems=problems)
        return PluginInspection(
            name=name,
            version=dist.version if dist is not None else "unknown",
            plugin=plugin,
            problems=tuple(problems),
        )
    return None


def _load(
    entry_point: importlib.metadata.EntryPoint,
    core_engine_api: str,
    *,
    log: bool,
    problems: list[str] | None = None,
) -> InstalledPlugin | None:
    dist = entry_point.dist
    name = _dist_name(entry_point)
    version = dist.version if dist is not None else "unknown"
    label = f"{name} {version}"
    try:
        manifest = entry_point.load()
    except Exception as exc:
        _skip(
            log,
            problems,
            label,
            f"its manifest {entry_point.value!r} cannot be loaded: {exc}",
        )
        return None
    if not isinstance(manifest, Mapping):
        _skip(
            log, problems, label, f"its manifest {entry_point.value!r} is not a mapping"
        )
        return None
    errors = _schema_errors(dict(manifest))
    if errors:
        _skip(
            log,
            problems,
            label,
            "its manifest fails plugin_manifest.schema.json: " + "; ".join(errors),
        )
        return None
    if manifest["core_engine_api"] != core_engine_api:
        _skip(
            log,
            problems,
            label,
            f"it was built for core_engine_api {manifest['core_engine_api']!r}; "
            f"this CORE supports {core_engine_api!r}",
        )
        return None
    root = _package_root(entry_point)
    return InstalledPlugin(
        name=name,
        version=version,
        core_engine_api=manifest["core_engine_api"],
        root=root,
        engines=tuple(
            _import_engines(
                label, manifest.get("engines") or [], log=log, problems=problems
            )
        ),
        catalogs=root / manifest["catalogs"] if manifest.get("catalogs") else None,
        packs=root / manifest["packs"] if manifest.get("packs") else None,
        fingerprint=fingerprint(dist),
    )


def _skip(log: bool, problems: list[str] | None, label: str, why: str) -> None:
    if problems is not None:
        problems.append(why)
    if not log:
        return
    logger.warning(
        "Plug-in %s is not loaded: %s. Rules that name its engines give the "
        "engine-missing finding (ADR-177 D4).",
        label,
        why,
    )


def _dist_name(entry_point: importlib.metadata.EntryPoint) -> str:
    dist = entry_point.dist
    return dist.metadata["Name"] if dist is not None else entry_point.name


def _package_root(entry_point: importlib.metadata.EntryPoint) -> Path:
    """The directory of the top-level package that holds the manifest; the
    manifest's ``catalogs`` and ``packs`` are relative to it."""
    top = entry_point.module.split(".", 1)[0]
    return Path(str(importlib.resources.files(top)))


def _import_engines(
    label: str, names: list[str], *, log: bool, problems: list[str] | None = None
) -> list[type]:
    engines: list[type] = []
    for target in names:
        module_name, _, class_name = target.partition(":")
        try:
            engines.append(getattr(importlib.import_module(module_name), class_name))
        except Exception as exc:
            if problems is not None:
                problems.append(f"engine {target} failed to import: {exc}")
            if not log:
                continue
            logger.warning(
                "Plug-in %s: engine %s failed to import: %s (ADR-176 D7)",
                label,
                target,
                exc,
            )
    return engines


def _schema_errors(manifest: dict[str, Any]) -> list[str]:
    from jsonschema.validators import validator_for

    schema = load_meta_schema(_SCHEMA_FILENAME)
    if schema is None:
        return [f"{_SCHEMA_FILENAME} not found"]
    validator = validator_for(schema)(schema)
    return sorted(error.message for error in validator.iter_errors(manifest))


# ID: 35f10e24-a7af-4fba-a960-94cc5a82e1b6
def load_meta_schema(filename: str) -> dict[str, Any] | None:
    """A format schema from the active ``.intent/META/``, else from the
    machinery floor shipped in the wheel."""
    candidates: list[Path] = []
    try:
        from shared.infrastructure.intent.intent_repository import get_intent_repository

        candidates.append(get_intent_repository().root / "META" / filename)
    except Exception as exc:
        logger.debug("Plug-ins: no intent repository (%s)", exc)
    try:
        floor = Path(str(importlib.resources.files("shared._machinery_floor")))
        candidates.append(floor / "META" / filename)
    except Exception as exc:
        logger.debug("Plug-ins: no machinery floor (%s)", exc)
    for candidate in candidates:
        if candidate.is_file():
            return json.loads(candidate.read_text(encoding="utf-8"))
    return None


# ID: e75d6138-956f-4b10-933c-2f22ec542a68
def fingerprint(dist: importlib.metadata.Distribution | None) -> str:
    """sha256 over the sorted (path, sha256 of content) pairs of the
    distribution's installed files, without compiled files and the install
    bookkeeping (``RECORD`` and the like), so a wheel and an editable install
    of the same files agree (ADR-177 D8)."""
    digest = hashlib.sha256()
    if dist is None:
        return "sha256:" + digest.hexdigest()
    pairs: list[tuple[str, str]] = []
    for file in dist.files or []:
        path = str(file).replace("\\", "/")
        if path.endswith(_FINGERPRINT_SKIP_SUFFIXES) or "__pycache__/" in path:
            continue
        if Path(path).name in _FINGERPRINT_SKIP_NAMES:
            continue
        located = Path(str(file.locate()))
        if not located.is_file():
            continue
        pairs.append((path, hashlib.sha256(located.read_bytes()).hexdigest()))
    for path, file_hash in sorted(pairs):
        digest.update(f"{path}\0{file_hash}\n".encode())
    return "sha256:" + digest.hexdigest()


def _log_loaded(plugin: InstalledPlugin) -> None:
    logger.info(
        "Plug-in %s loaded: core_engine_api %s, engines [%s], catalogs %d, packs %d, "
        "fingerprint %s (ADR-177 D8)",
        plugin.label,
        plugin.core_engine_api,
        ", ".join(getattr(e, "engine_id", e.__name__) for e in plugin.engines),
        _count(plugin.catalogs, "catalog.yaml"),
        _count(plugin.packs, "*.yaml"),
        plugin.fingerprint,
    )


def _count(directory: Path | None, pattern: str) -> int:
    if directory is None or not directory.is_dir():
        return 0
    return sum(1 for _ in directory.rglob(pattern))


__all__ = [
    "CORE_ENGINE_API",
    "ENTRY_POINT_GROUP",
    "InstalledPlugin",
    "PluginInspection",
    "fingerprint",
    "inspect_plugin",
    "installed_plugins",
    "load_meta_schema",
]
