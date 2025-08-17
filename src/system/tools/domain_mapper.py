# src/system/tools/domain_mapper.py
"""
Maps file paths to logical domains based on project structure configuration.
"""
from pathlib import Path
from typing import Dict

from shared.config_loader import load_config
from shared.logger import getLogger

log = getLogger(__name__)


class DomainMapper:
    """Maps file paths to logical domains based on project structure."""

    def __init__(self, root_path: Path):
        """Initializes the mapper, always resolving paths to be absolute."""
        self.root_path = root_path.resolve()
        self.src_root = self.root_path / "src"
        # The map will now store absolute, resolved Path objects as keys.
        self.domain_map_abs: Dict[Path, str] = self._load_domain_map()

    def _load_domain_map(self) -> Dict[Path, str]:
        """Loads the domain-to-path mapping, resolving all paths to be absolute."""
        path = self.root_path / ".intent" / "knowledge" / "source_structure.yaml"
        data = load_config(path, "yaml")

        if not data or "structure" not in data:
            return self._infer_domains_from_directory_structure()

        structure = data.get("structure", [])
        # Convert all declared paths to absolute, resolved paths for unambiguous matching.
        return {
            (self.root_path / e["path"]).resolve(): e["domain"]
            for e in structure
            if "path" in e and "domain" in e
        }

    def _infer_domains_from_directory_structure(self) -> Dict[Path, str]:
        """A heuristic to guess domains if source_structure.yaml is missing."""
        log.warning(
            "source_structure.yaml not found. Falling back to directory-based domain inference."
        )
        if not self.src_root.is_dir():
            log.warning("`src` directory not found. Cannot infer domains.")
            return {}

        domain_map = {}
        for item in self.src_root.iterdir():
            if item.is_dir() and not item.name.startswith(("_", ".")):
                # Store the absolute, resolved path as the key.
                domain_map[item.resolve()] = item.name
        log.info(
            f"   -> Inferred {len(domain_map)} domains from `src/` directory structure."
        )
        return domain_map

    def determine_domain(self, file_path_relative: Path) -> str:
        """
        Determines the logical domain for a file path using absolute path matching.
        The input `file_path_relative` is expected to be relative to self.root_path.
        """
        full_path = (self.root_path / file_path_relative).resolve()
        sorted_domain_paths = sorted(
            self.domain_map_abs.keys(), key=lambda p: len(p.parts), reverse=True
        )

        for domain_root in sorted_domain_paths:
            # Use Path.relative_to() in a try-except block. This is the most
            # robust way to check if a path is within another path's tree.
            try:
                full_path.relative_to(domain_root)
                # If the line above doesn't raise a ValueError, we have a match.
                return self.domain_map_abs[domain_root]
            except ValueError:
                # This means full_path is not under domain_root, so we continue.
                continue

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
