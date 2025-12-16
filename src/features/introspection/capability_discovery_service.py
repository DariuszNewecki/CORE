# src/features/introspection/capability_discovery_service.py

"""
Refactored under dry_by_design.
Pattern: move_function.
Removed local _load_yaml in favor of the canonical implementation from shared.config_loader.

CORE SEMANTICS:
- `domain`     → authoritative, human-governed, finite (top-level only)
- `subdomain`  → non-authoritative namespace (LLM-assigned, advisory only)
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


# ----------------------------
# Capability key semantics
# ----------------------------


def _split_capability_key(key: str) -> tuple[str, str | None]:
    """
    Split a capability key into (domain, namespace).

    RULES (constitutional):
    - domain is the ONLY authority boundary
    - namespace is informational only
    - namespace MUST NOT be used for access control, ownership, or governance
    """
    if "." not in key:
        return key, None
    domain, namespace = key.split(".", 1)
    return domain, namespace or None


# ----------------------------
# Registry
# ----------------------------


# ID: a3e2c0e1-ab3a-4384-ad7d-e65025a70789
class CapabilityRegistry:
    """
    Holds canonical capability keys and alias mapping.
    """

    def __init__(self, canonical: set[str], aliases: dict[str, str]):
        self.canonical = set(canonical)
        self.aliases = dict(aliases)

    # ID: 8910cd7d-01b5-4bf4-87ff-b37733a82532
    def resolve(self, tag: str) -> str | None:
        if tag in self.canonical:
            return tag
        return self.aliases.get(tag)


# ----------------------------
# Load helpers
# ----------------------------


def _iter_capability_files(base: Path) -> Iterable[Path]:
    if not base.exists():
        return []
    for p in sorted(base.glob("**/*")):
        if p.is_dir():
            if p.name == "schemas":
                continue
            continue
        if p.suffix.lower() in {".yaml", ".yml"}:
            yield p


def _extract_canonical_from_doc(doc: dict) -> set[str]:
    canonical: set[str] = set()
    tags = doc.get("tags", [])
    if isinstance(tags, list):
        for item in tags:
            if isinstance(item, dict) and isinstance(item.get("key"), str):
                canonical.add(item["key"])
    return canonical


def _extract_aliases_from_doc(doc: dict) -> dict[str, str]:
    aliases: dict[str, str] = {}
    raw = doc.get("aliases")
    if isinstance(raw, dict):
        for k, v in raw.items():
            if isinstance(k, str) and isinstance(v, str) and k and v:
                aliases[k] = v
    return aliases


def _detect_alias_cycles(aliases: dict[str, str]) -> list[list[str]]:
    visited: set[str] = set()
    stack: set[str] = set()
    cycles: list[list[str]] = []

    # ID: bb444376-1add-4bba-a29d-b7e987e44073
    def dfs(node: str, path: list[str]):
        visited.add(node)
        stack.add(node)
        nxt = aliases.get(node)
        if nxt:
            if nxt not in visited:
                dfs(nxt, path + [nxt])
            elif nxt in stack and nxt in path:
                idx = path.index(nxt)
                cycles.append(path[idx:] + [nxt])
        stack.remove(node)

    for a in aliases:
        if a not in visited:
            dfs(a, [a])

    return cycles


# ----------------------------
# Constitution loader
# ----------------------------


# ID: d6bd862e-8278-4967-bf95-e83bdd5ad576
def load_and_validate_capabilities(intent_dir: Path) -> CapabilityRegistry:
    base = intent_dir / "knowledge" / "capability_tags"
    if not base.exists():
        raise FileNotFoundError(f"Capability tags directory not found: {base}")

    canonical: set[str] = set()
    aliases: dict[str, str] = {}

    for path in _iter_capability_files(base):
        doc = load_yaml_file(path)
        canonical |= _extract_canonical_from_doc(doc)
        aliases.update(_extract_aliases_from_doc(doc))

    cycles = _detect_alias_cycles(aliases)
    if cycles:
        raise ValueError(f"Alias cycle(s) detected: {cycles}")

    unresolved = [(a, t) for a, t in aliases.items() if t not in canonical]
    if unresolved:
        raise ValueError(
            "Alias targets do not map to canonical capabilities:\n"
            + "\n".join(f"{a} → {t}" for a, t in unresolved)
        )

    return CapabilityRegistry(canonical, aliases)


# ----------------------------
# Validation
# ----------------------------


# ID: bbfb9527-fa8e-4b68-b5c4-b38c94133d1e
def validate_agent_roles(agent_roles: dict, registry: CapabilityRegistry) -> None:
    roles = agent_roles.get("roles", {})
    if not isinstance(roles, dict):
        raise ValueError("agent_roles must contain a 'roles' mapping")

    errors: list[str] = []
    for role, cfg in roles.items():
        for tag in cfg.get("allowed_tags", []):
            if not registry.resolve(tag):
                errors.append(f"{role}: unknown capability '{tag}'")

    if errors:
        raise ValueError("Invalid capability references:\n" + "\n".join(errors))


# ----------------------------
# Discovery
# ----------------------------


# ID: 2b7449f9-dbac-4f09-9948-2be669b42fec
def collect_code_capabilities(
    root: Path,
    include_globs: list[str],
    exclude_globs: list[str],
    require_kgb: bool,
) -> dict[str, CapabilityMeta]:
    from features.introspection.discovery.from_kgb import _collect_from_kgb
    from features.introspection.discovery.from_source_scan import (
        collect_from_source_scan,
    )

    try:
        return (
            _collect_from_kgb(root)
            if require_kgb
            else collect_from_source_scan(root, include_globs, exclude_globs)
        )
    except Exception as e:
        logger.warning("Capability discovery failed: %s", e, exc_info=True)
        return {}


# ----------------------------
# DB sync
# ----------------------------


# ID: ba659030-b38a-4be3-ae9c-fce21f68cd59
async def sync_capabilities_to_db(
    db: AsyncSession,
    intent_dir: Path,
) -> tuple[int, list[str]]:
    """
    Sync constitutional capabilities into DB.

    Authority boundary:
    - domain     → enforced
    - subdomain  → namespace only
    """
    registry = load_and_validate_capabilities(intent_dir)
    upserted = 0

    for key in registry.canonical:
        domain, namespace = _split_capability_key(key)
        title = key.replace(".", " ").replace("_", " ").title()

        stmt = text(
            """
            INSERT INTO core.capabilities
                (name, domain, subdomain, title, owner, status, tags, updated_at)
            VALUES
                (:name, :domain, :subdomain, :title, 'constitution', 'Active', :tags, NOW())
            ON CONFLICT (domain, name) DO UPDATE SET
                subdomain = EXCLUDED.subdomain,
                status = 'Active',
                updated_at = NOW()
            """
        )

        await db.execute(
            stmt,
            {
                "name": key,
                "domain": domain,
                "subdomain": namespace,
                "title": title,
                "tags": json.dumps(["constitutional"]),
            },
        )
        upserted += 1

    await db.commit()
    logger.info("Synced %s capabilities", upserted)
    return upserted, []
