# src/features/introspection/capability_discovery_service.py
# ID: 44ed58de-ba54-44ed-9392-3117fd5d446c
"""
Capability Discovery Service - Refactored for High Fidelity (V2.3).
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from shared.config_loader import load_yaml_file
from shared.logger import getLogger
from shared.models import CapabilityMeta

from .discovery import loader, sync

# 1. FIXED: Proper import to avoid shadowing/type expression errors
from .discovery.registry import CapabilityRegistry


logger = getLogger(__name__)


# ID: d6bd862e-8278-4967-bf95-e83bdd5ad576
def load_and_validate_capabilities(intent_dir: Path) -> CapabilityRegistry:
    base = intent_dir / "knowledge" / "capability_tags"
    if not base.exists():
        raise FileNotFoundError(f"Capability tags directory not found: {base}")

    canonical: set[str] = set()
    aliases: dict[str, str] = {}

    for path in loader._iter_capability_files(base):
        doc = load_yaml_file(path)
        canonical |= loader._extract_canonical_from_doc(doc)
        aliases.update(loader._extract_aliases_from_doc(doc))

    if cycles := loader._detect_alias_cycles(aliases):
        raise ValueError(f"Alias cycle(s) detected: {cycles}")

    unresolved = [(a, t) for a, t in aliases.items() if t not in canonical]
    if unresolved:
        raise ValueError(
            "Alias targets do not map to canonical capabilities:\n"
            + "\n".join(f"{a} → {t}" for a, t in unresolved)
        )

    return CapabilityRegistry(canonical, aliases)


# ID: ba659030-b38a-4be3-ae9c-fce21f68cd59
async def sync_capabilities_to_db(
    db: AsyncSession, intent_dir: Path
) -> tuple[int, list[str]]:
    registry = load_and_validate_capabilities(intent_dir)
    count = await sync.run_capability_upsert(db, registry.canonical)
    await db.commit()
    logger.info("Synced %s capabilities", count)
    return count, []


# ID: 2b7449f9-dbac-4f09-9948-2be669b42fec
def collect_code_capabilities(
    root: Path, include_globs: list[str], exclude_globs: list[str], require_kgb: bool
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


# ID: bbfb9527-fa8e-4b68-b5c4-b38c94133d1e
def validate_agent_roles(agent_roles: dict, registry: CapabilityRegistry) -> None:
    roles = agent_roles.get("roles", {})
    if not isinstance(roles, dict):
        raise ValueError("agent_roles must contain a 'roles' mapping")

    errors = [
        f"{role}: unknown capability '{tag}'"
        for role, cfg in roles.items()
        for tag in cfg.get("allowed_tags", [])
        if not registry.resolve(tag)
    ]

    if errors:
        raise ValueError("Invalid capability references:\n" + "\n".join(errors))


# Re-export the class name for backward compatibility without breaking type hints
__all__ = [
    "CapabilityRegistry",
    "collect_code_capabilities",
    "load_and_validate_capabilities",
    "sync_capabilities_to_db",
    "validate_agent_roles",
]
