# src/shared/infrastructure/intent/pack_loader.py

"""
Governance Pack Loader — reads the top-level packs/*.yaml registry and extracts
rule definitions and enforcement mappings for adoption into a consumer repo.
Packs are adoptable products, not CORE's own law, and live outside .intent/
(ADR-149).

CONSTITUTIONAL:
- Read-only: no writes, no side effects.
- Shared infrastructure layer. Must not import mind/, body/, or will/.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from shared.logger import getLogger
from shared.processors.yaml_processor import strict_yaml_processor


logger = getLogger(__name__)

CORE_ROLE = "catalog"  # ADR-095 D3


@dataclass(frozen=True)
# ID: b646137e-6410-4bc4-a023-29c1cd18286a
class LoadedPack:
    """A governance pack loaded from a packs/*.yaml declaration.

    rules: list of rule dicts (rule_document.schema.json item shape).
    enforcement_mappings: dict of rule_id → mapping dict (enforcement_mapping.schema.json shape).
    """

    pack_id: str
    version: str
    title: str
    description: str
    level: str
    target_language: str | None
    compatibility_floor: str | None
    supersedes: str | None
    rules: list[dict[str, Any]] = field(default_factory=list)
    enforcement_mappings: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    # ID: e0087cee-79f9-4b29-9c9a-21f8503a7ff2
    def rule_ids(self) -> set[str]:
        return {r["id"] for r in self.rules if "id" in r}


# ID: 0ce30db0-92c8-4c3b-a4d9-de7e71bec842
class PackLoader:
    """Load and validate governance packs from a packs directory.

    Typically pointed at the top-level packs/ registry in the CORE installation
    (a sibling of .intent/, per ADR-149). Each YAML file in the directory is
    treated as one pack declaration and must conform to
    META/governance_pack.schema.json.
    """

    def __init__(self, packs_dir: Path) -> None:
        self._packs_dir = packs_dir

    # ID: c71a38cb-9bfe-4d80-96c4-11c032b7f4f3
    def list_pack_ids(self) -> list[str]:
        """Return all pack IDs discoverable from the packs directory."""
        if not self._packs_dir.exists():
            return []
        ids: list[str] = []
        for path in sorted(self._packs_dir.glob("*.yaml")):
            try:
                data = strict_yaml_processor.load_strict(path)
                pack_id = data.get("id")
                if pack_id:
                    ids.append(str(pack_id))
            except Exception as exc:
                logger.warning("pack_loader: skipping %s: %s", path.name, exc)
        return ids

    # ID: 57f94520-8177-4fc8-a56d-d69b90bd7314
    def load_pack(self, pack_id: str) -> LoadedPack | None:
        """Load a single pack by its declared `id` field.

        Returns None when no pack file declares that id. Logs a warning for
        files that cannot be parsed.
        """
        if not self._packs_dir.exists():
            return None
        for path in sorted(self._packs_dir.glob("*.yaml")):
            try:
                data = strict_yaml_processor.load_strict(path)
            except Exception as exc:
                logger.warning("pack_loader: error reading %s: %s", path.name, exc)
                continue
            if data.get("id") == pack_id:
                return self._build(data, path)
        return None

    # ID: a24c1264-e474-4131-a15e-cc08073a3ac9
    def load_all(self) -> list[LoadedPack]:
        """Load every pack found in the packs directory."""
        if not self._packs_dir.exists():
            return []
        packs: list[LoadedPack] = []
        for path in sorted(self._packs_dir.glob("*.yaml")):
            try:
                data = strict_yaml_processor.load_strict(path)
                if data.get("kind") != "governance_pack":
                    logger.debug(
                        "pack_loader: skipping %s (kind=%s)",
                        path.name,
                        data.get("kind"),
                    )
                    continue
                packs.append(self._build(data, path))
            except Exception as exc:
                logger.warning("pack_loader: error reading %s: %s", path.name, exc)
        logger.info(
            "PackLoader: loaded %d pack(s) from %s", len(packs), self._packs_dir
        )
        return packs

    def _build(self, data: dict[str, Any], path: Path) -> LoadedPack:
        pack_id = data.get("id", "")
        if not pack_id:
            raise ValueError(f"Pack file {path.name} is missing required 'id' field")
        if data.get("kind") != "governance_pack":
            raise ValueError(
                f"Pack file {path.name} has kind={data.get('kind')!r}; expected 'governance_pack'"
            )
        return LoadedPack(
            pack_id=str(pack_id),
            version=str(data.get("version", "0.0.0")),
            title=str(data.get("title", pack_id)),
            description=str(data.get("description", "")),
            level=str(data.get("level", "starter")),
            target_language=data.get("target_language") or None,
            compatibility_floor=data.get("compatibility_floor") or None,
            supersedes=data.get("supersedes") or None,
            rules=list(data.get("rules") or []),
            enforcement_mappings=dict(data.get("enforcement_mappings") or {}),
        )
