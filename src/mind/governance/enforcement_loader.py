# src/mind/governance/enforcement_loader.py
"""
Enforcement Mapping Loader

Loads enforcement strategies from derived artifacts (.intent/enforcement/).
This is the derivation boundary: Constitution → Implementation.

CONSTITUTIONAL ALIGNMENT:
- Enforcement mappings are DERIVED ARTIFACTS, not law
- Missing mappings = "declared but not implementable" (safe degradation)
- Mappings can change without constitutional amendment

CONSTITUTIONAL FIX:
- Removed forbidden placeholder to satisfy 'purity.no_todo_placeholders'.
- Assigned stable UUID for module-level identification.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from shared.logger import getLogger
from shared.processors.yaml_processor import strict_yaml_processor


logger = getLogger(__name__)


# ID: ba8928ab-8be6-4945-8c85-68a6da9fc606
class EnforcementMappingLoader:
    """
    Loads enforcement mappings with preset resolution and caching.
    Handles hundreds/thousands of rules efficiently.

    Design principles:
    - Lazy loading: Load files only when needed
    - Preset resolution: DRY for common scope patterns
    - Caching: Avoid re-parsing the same files
    - Graceful degradation: Missing mappings don't break the system
    """

    def __init__(self, intent_root: Path):
        """
        Initialize the loader.

        Args:
            intent_root: Path to .intent directory
        """
        self.intent_root = intent_root
        self.enforcement_dir = intent_root / "enforcement"

        # Caches
        self._presets: dict[str, dict[str, Any]] = {}
        self._mappings_cache: dict[str, dict[str, Any]] = {}
        self._loaded_files: set[Path] = set()

        logger.debug(
            "EnforcementMappingLoader initialized (enforcement_dir=%s)",
            self.enforcement_dir,
        )

    # ID: aeeccff5-3063-421e-b373-3fa65b282550
    def load_all_mappings(self) -> dict[str, dict[str, Any]]:
        """
        Load all enforcement mappings from all domain directories.

        Returns:
            Dict mapping rule_id -> enforcement strategy
        """
        if self._mappings_cache:
            logger.debug("Using cached enforcement mappings")
            return self._mappings_cache

        mappings_dir = self.enforcement_dir / "mappings"

        if not mappings_dir.exists():
            logger.warning(
                "Enforcement mappings directory not found: %s. "
                "All rules will be declared-only (not implementable).",
                mappings_dir,
            )
            return {}

        # Walk directory tree, load all .yaml files
        for yaml_file in mappings_dir.rglob("*.yaml"):
            if yaml_file in self._loaded_files:
                continue

            try:
                domain_mappings = self._load_mapping_file(yaml_file)
                self._mappings_cache.update(domain_mappings)
                self._loaded_files.add(yaml_file)
            except Exception as e:
                logger.error(
                    "Failed to load enforcement mapping file %s: %s", yaml_file, e
                )

        logger.info(
            "Loaded %d enforcement mappings from %d files",
            len(self._mappings_cache),
            len(self._loaded_files),
        )

        return self._mappings_cache

    # ID: 26088305-a101-4ffb-91b4-ffa21214727f
    def get_enforcement_strategy(self, rule_id: str) -> dict[str, Any] | None:
        """
        Get enforcement strategy for a specific rule.

        Args:
            rule_id: The rule identifier (e.g., "architecture.max_file_size")

        Returns:
            Enforcement strategy dict or None if not mapped
        """
        if not self._mappings_cache:
            self.load_all_mappings()

        return self._mappings_cache.get(rule_id)

    def _load_mapping_file(self, path: Path) -> dict[str, dict[str, Any]]:
        """
        Load a single mapping file with preset resolution.

        Args:
            path: Path to YAML mapping file

        Returns:
            Dict of rule_id -> enforcement strategy
        """
        logger.debug("Loading enforcement mapping file: %s", path)

        data = strict_yaml_processor.load_strict(path)

        # Load presets referenced in this file
        presets_block = data.get("presets", {})
        for preset_name, preset_ref in presets_block.items():
            if preset_name not in self._presets:
                self._presets[preset_name] = self._load_preset(preset_ref)

        # Resolve scope references in mappings
        mappings = data.get("mappings", {})
        for rule_id, strategy in mappings.items():
            scope = strategy.get("scope")

            # If scope is a reference, resolve it
            if isinstance(scope, str) and scope.startswith("!ref "):
                preset_name = scope.replace("!ref ", "").strip()
                if preset_name in self._presets:
                    strategy["scope"] = self._presets[preset_name]
                else:
                    logger.warning(
                        "Unknown preset reference '%s' in rule %s (file: %s)",
                        preset_name,
                        rule_id,
                        path,
                    )
                    # Fallback to safe default
                    strategy["scope"] = {"applies_to": ["src/**/*.py"]}

        logger.debug("Loaded %d mappings from %s", len(mappings), path.name)
        return mappings

    def _load_preset(self, preset_name: str) -> dict[str, Any]:
        """
        Load a scope preset from the presets directory.

        Args:
            preset_name: Name of the preset (e.g., "python_source")

        Returns:
            Preset definition dict
        """
        preset_file = self.enforcement_dir / "presets" / f"{preset_name}.yaml"

        if not preset_file.exists():
            logger.warning("Preset file not found: %s", preset_file)
            # Return safe default
            return {"name": preset_name, "applies_to": ["src/**/*.py"]}

        try:
            preset = strict_yaml_processor.load_strict(preset_file)
            logger.debug("Loaded preset: %s", preset_name)
            return preset
        except Exception as e:
            logger.error("Failed to load preset %s: %s", preset_name, e)
            # Return safe default
            return {"name": preset_name, "applies_to": ["src/**/*.py"]}

    # ID: 681251eb-0ab4-4fc4-bc90-376a98e54e6f
    def list_all_mapped_rules(self) -> list[str]:
        """
        Get list of all rule IDs that have enforcement mappings.

        Returns:
            Sorted list of rule IDs
        """
        if not self._mappings_cache:
            self.load_all_mappings()

        return sorted(self._mappings_cache.keys())

    # ID: d52e4519-8c6e-4fd4-bf59-ecd996364c70
    def get_stats(self) -> dict[str, int]:
        """
        Get statistics about loaded mappings.

        Returns:
            Dict with stats (total_mappings, total_files, engines_used, etc.)
        """
        if not self._mappings_cache:
            self.load_all_mappings()

        engines = set()
        for strategy in self._mappings_cache.values():
            engines.add(strategy.get("engine", "unknown"))

        return {
            "total_mappings": len(self._mappings_cache),
            "total_files": len(self._loaded_files),
            "total_presets": len(self._presets),
            "engines_used": len(engines),
        }


__all__ = ["EnforcementMappingLoader"]
