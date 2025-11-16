# src/features/introspection/capability_discovery_service.py

"""
Refactored under dry_by_design.
Pattern: move_function.
Removed local _load_yaml in favor of the canonical implementation from shared.config_loader.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from shared.config_loader import load_yaml_file
from shared.logger import getLogger
from shared.models import CapabilityMeta

logger = getLogger(__name__)


# ID: 7ab95b32-3d81-4094-8b7f-6a4386a68bb7
class CapabilityRegistry:
    """
    Holds the canonical capability keys and alias mapping.
    Provides simple resolution (canonical → itself, alias → canonical).
    """

    def __init__(self, canonical: set[str], aliases: dict[str, str]):
        """Initializes the registry with canonical tags and an alias map."""
        self.canonical: set[str] = set(canonical)
        self.aliases: dict[str, str] = dict(aliases)

    # ID: c04bc1da-dc61-47e2-ab72-ca2fe4d7b772
    def resolve(self, tag: str) -> str | None:
        """
        Return canonical capability if `tag` is known, otherwise None.
        Resolution is single-hop (alias -> canonical).
        """
        if tag in self.canonical:
            return tag
        return self.aliases.get(tag)


def _iter_capability_files(base: Path) -> Iterable[Path]:
    """
    Yields YAML files under capability_tags/, ignoring schema and non-yaml files.
    """
    if not base.exists():
        return []
    for p in sorted(base.glob("**/*")):
        if p.is_dir():
            if p.name in {"schemas"}:
                continue
            continue
        if p.suffix.lower() in {".yaml", ".yml"}:
            yield p


def _extract_canonical_from_doc(doc: dict) -> set[str]:
    """
    Extracts canonical capability keys from a domain manifest file.
    """
    canonical: set[str] = set()
    tags = doc.get("tags", [])
    if isinstance(tags, list):
        for item in tags:
            if (
                isinstance(item, dict)
                and "key" in item
                and isinstance(item["key"], str)
            ):
                canonical.add(item["key"])
    return canonical


def _extract_aliases_from_doc(doc: dict) -> dict[str, str]:
    """
    Extracts aliases from a manifest file.
    """
    aliases: dict[str, str] = {}
    raw = doc.get("aliases")
    if isinstance(raw, dict):
        for k, v in raw.items():
            if isinstance(k, str) and isinstance(v, str) and k and v:
                aliases[k] = v
    return aliases


def _merge_sets(*sets: Iterable[str]) -> set[str]:
    """Merges multiple iterables into a single set."""
    acc: set[str] = set()
    for s in sets:
        acc.update(s)
    return acc


def _detect_alias_cycles(aliases: dict[str, str]) -> list[list[str]]:
    """Detects simple cycles in the alias graph."""
    visited: set[str] = set()
    stack: set[str] = set()
    cycles: list[list[str]] = []

    # ID: 9eda4fea-f45e-486b-bec5-dc28c8231907
    def dfs(node: str, path: list[str]):
        visited.add(node)
        stack.add(node)
        nxt = aliases.get(node)
        if nxt:
            if nxt not in visited:
                dfs(nxt, path + [nxt])
            elif nxt in stack:
                if nxt in path:
                    idx = path.index(nxt)
                    cycles.append(path[idx:] + [nxt])
        stack.remove(node)

    for a in aliases:
        if a not in visited:
            dfs(a, [a])
    return cycles


# ID: 00b0e51d-5808-4525-84c1-60027d5efc12
def load_and_validate_capabilities(intent_dir: Path) -> CapabilityRegistry:
    """
    Loads and validates all canonical capabilities and aliases.
    """
    base = intent_dir / "knowledge" / "capability_tags"
    canonical_tags: set[str] = set()
    alias_map: dict[str, str] = {}
    if not base.exists():
        raise FileNotFoundError(f"Capability tags directory not found: {base}")
    for path in _iter_capability_files(base):
        try:
            doc = load_yaml_file(path)
        except Exception as e:
            raise ValueError(f"Failed to load capability YAML: {path} ({e})") from e
        canonical_tags |= _extract_canonical_from_doc(doc)
        alias_map.update(_extract_aliases_from_doc(doc))
    cycles = _detect_alias_cycles(alias_map)
    if cycles:
        formatted = "; ".join(" -> ".join(c) for c in cycles)
        raise ValueError(f"Alias cycle(s) detected: {formatted}")
    unresolved = [(a, t) for a, t in alias_map.items() if t not in canonical_tags]
    if unresolved:
        lines = "\n - ".join((f"'{a}' → '{t}'" for a, t in unresolved))
        raise ValueError(
            "Alias targets that do not map to a canonical capability:\n - " + lines
        )
    return CapabilityRegistry(canonical=canonical_tags, aliases=alias_map)


# ID: 4902698e-fea7-436b-bd3b-289ab279dd15
def validate_agent_roles(agent_roles: dict, registry: CapabilityRegistry) -> None:
    """Validates agent role configurations against the capability registry."""
    errors: list[str] = []
    roles = agent_roles.get("roles", {})
    if not isinstance(roles, dict):
        raise ValueError("agent_roles must contain a 'roles' mapping")
    for role, cfg in roles.items():
        allowed = cfg.get("allowed_tags", [])
        for tag in allowed:
            if not registry.resolve(tag):
                errors.append(
                    f"Role '{role}' references unknown capability tag '{tag}'"
                )
    if errors:
        joined = "\n - ".join(errors)
        raise ValueError(
            "Agent role configuration contains unresolved/invalid capability tags:\n - "
            + joined
        )


# ID: ccb0e95b-03e9-447b-931f-b6a665355392
def collect_code_capabilities(
    root: Path, include_globs: list[str], exclude_globs: list[str], require_kgb: bool
) -> dict[str, CapabilityMeta]:
    """Unified discovery entrypoint."""
    from features.introspection.discovery.from_kgb import collect_from_kgb
    from features.introspection.discovery.from_source_scan import (
        collect_from_source_scan,
    )

    try:
        if require_kgb:
            return collect_from_kgb(root)
        return collect_from_source_scan(root, include_globs, exclude_globs)
    except Exception as e:
        logger.warning(
            f"Capability discovery failed: {e}. Returning empty.", exc_info=True
        )
        return {}
