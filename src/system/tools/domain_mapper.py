# src/system/tools/domain_mapper.py
import logging
from pathlib import Path
from typing import Dict

# Corrected import path
from shared.config_loader import load_config

logger = logging.getLogger(__name__)


class DomainMapper:
    """Maps source files to their architectural domains based on directory structure."""

    def __init__(self, root_path: Path):
        """Initialize the instance with a root path, resolved domain map, and sorted domain paths."""
        self.root_path = Path(root_path).resolve()
        # The map will now store relative Path objects as keys.
        self.domain_map_relative: Dict[Path, str] = self._load_domain_map()
        # Sort by depth (deepest first) for proper matching precedence
        self.sorted_domain_paths = sorted(
            self.domain_map_relative.keys(), key=lambda p: len(p.parts), reverse=True
        )

    def _load_domain_map(self) -> Dict[Path, str]:
        """
        Load domain mappings from source_structure.yaml.
        Returns a dictionary mapping relative paths to domain names.
        This avoids resolve() issues by working entirely in relative space.
        """
        config_path = self.root_path / ".intent" / "knowledge" / "source_structure.yaml"

        try:
            data = load_config(config_path, "yaml")
        except Exception as e:
            logger.warning(
                f"Could not load domain configuration from {config_path}: {e}"
            )
            return {}

        # The key name in your file is 'structure', not 'source_structure'
        structure = data.get("structure")
        if not isinstance(structure, list):
            logger.warning("source_structure.yaml is missing a 'structure' list.")
            return {}

        domain_map = {}
        for entry in structure:
            if not isinstance(entry, dict):
                continue

            path_str = entry.get("path")
            domain = entry.get("domain")

            if not path_str or not domain:
                continue

            # Convert to Path and normalize - but keep as relative path
            relative_path = Path(path_str)
            if relative_path.is_absolute():
                # Gracefully handle incorrect absolute paths in config
                relative_path = (
                    Path(*relative_path.parts[1:]) if relative_path.parts else Path(".")
                )

            domain_map[relative_path] = domain

        logger.debug(f"Loaded {len(domain_map)} domain mappings: {domain_map}")
        return domain_map

    def determine_domain(self, file_path_relative: Path) -> str:
        """
        Determine the domain for a file given its relative path from root.

        Args:
            file_path_relative: Path relative to the repository root

        Returns:
            Domain name or "unassigned" if no match found
        """
        if not isinstance(file_path_relative, Path):
            file_path_relative = Path(file_path_relative)

        if file_path_relative.is_absolute():
            try:
                file_path_relative = file_path_relative.relative_to(self.root_path)
            except ValueError:
                logger.warning(
                    f"Cannot make {file_path_relative} relative to {self.root_path}"
                )
                return "unassigned"

        # Find the most specific (deepest) domain that contains this file
        for domain_path in self.sorted_domain_paths:
            try:
                # Check if the file is under this domain path
                file_path_relative.relative_to(domain_path)
                domain = self.domain_map_relative[domain_path]
                logger.debug(
                    f"File {file_path_relative} mapped to domain '{domain}' via {domain_path}"
                )
                return domain
            except ValueError:
                # File is not under this domain path, continue searching
                continue

        logger.debug(f"File {file_path_relative} could not be mapped to any domain")
        return "unassigned"

    def infer_agent_from_path(self, relative_path: Path) -> str:
        """Infers the most likely responsible agent based on keywords in the file path."""
        path_lower = str(relative_path).lower()

        agent_keywords = {
            "planner": "planner_agent",
            "generator": "generator_agent",
            "core": "core_agent",
            "tool": "tooling_agent",
        }

        for keyword, agent in agent_keywords.items():
            if keyword in path_lower:
                return agent

        if any(x in path_lower for x in ["validator", "guard", "audit"]):
            return "validator_agent"

        return "generic_agent"
