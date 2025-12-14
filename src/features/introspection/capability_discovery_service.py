# src/features/introspection/capability_discovery_service.py

"""
Refactored under dry_by_design.
Pattern: move_function.
Removed local _load_yaml in favor of the canonical implementation from shared.config_loader.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config_loader import load_yaml_file
from shared.logger import getLogger
from shared.models import CapabilityMeta


logger = getLogger(__name__)


# ID: a3e2c0e1-ab3a-4384-ad7d-e65025a70789
class CapabilityRegistry:
    """
    Holds the canonical capability keys and alias mapping.
    Provides simple resolution (canonical → itself, alias → canonical).
    """

    def __init__(self, canonical: set[str], aliases: dict[str, str]):
        """Initializes the registry with canonical tags and an alias map."""
        self.canonical: set[str] = set(canonical)
        self.aliases: dict[str, str] = dict(aliases)

    # ID: 8910cd7d-01b5-4bf4-87ff-b37733a82532
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

    # ID: bf3dc676-a603-4087-a7a3-788bcfbd9a1c
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


# ID: d6bd862e-8278-4967-bf95-e83bdd5ad576
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


# ID: bbfb9527-fa8e-4b68-b5c4-b38c94133d1e
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


# ID: 2b7449f9-dbac-4f09-9948-2be669b42fec
def collect_code_capabilities(
    root: Path, include_globs: list[str], exclude_globs: list[str], require_kgb: bool
) -> dict[str, CapabilityMeta]:
    """Unified discovery entrypoint."""
    from features.introspection.discovery.from_kgb import _collect_from_kgb
    from features.introspection.discovery.from_source_scan import (
        collect_from_source_scan,
    )

    try:
        if require_kgb:
            return _collect_from_kgb(root)
        return collect_from_source_scan(root, include_globs, exclude_globs)
    except Exception as e:
        logger.warning(
            "Capability discovery failed: %s. Returning empty.", e, exc_info=True
        )
        return {}


# ID: ba659030-b38a-4be3-ae9c-fce21f68cd59
async def sync_capabilities_to_db(
    db: AsyncSession, intent_dir: Path
) -> tuple[int, list[str]]:
    """
    Synchronizes capability definitions from the Constitution (.intent)
    into the Database (core.capabilities).

    Returns:
        Tuple[int, list[str]]: (count of upserted capabilities, list of errors)
    """
    logger.info("Synchronizing capabilities from constitution to database...")
    try:
        registry = load_and_validate_capabilities(intent_dir)
    except FileNotFoundError:
        msg = "No capability tags directory found. Skipping sync."
        logger.warning(msg)
        return (0, [msg])
    except ValueError as e:
        msg = f"Constitution Error: {e}"
        logger.error(msg)
        return (0, [msg])
    capabilities_to_sync = list(registry.canonical)
    upserted_count = 0
    for cap_name in capabilities_to_sync:
        domain = cap_name.split(".")[0] if "." in cap_name else "general"
        title = cap_name.replace(".", " ").replace("_", " ").title()
        stmt = text(
            "\n            INSERT INTO core.capabilities (name, domain, title, owner, status, tags, updated_at)\n            VALUES (:name, :domain, :title, 'constitution', 'Active', :tags, NOW())\n            ON CONFLICT (domain, name) DO UPDATE SET\n                status = 'Active',\n                updated_at = NOW()\n            RETURNING id\n        "
        )
        await db.execute(
            stmt,
            {
                "name": cap_name,
                "domain": domain,
                "title": title,
                "tags": json.dumps(["constitutional"]),
            },
        )
        upserted_count += 1
    await db.commit()
    logger.info("Synced %s capabilities to DB", upserted_count)
    return (upserted_count, [])
