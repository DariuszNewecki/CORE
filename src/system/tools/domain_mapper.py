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
        """Initialize the instance with root_path, setting src_root and loading domain_map."""
        self.root_path = root_path
        self.src_root = self.root_path / "src"
        self.domain_map = self._load_domain_map()

    def _load_domain_map(self) -> Dict[str, str]:
        """Loads the domain-to-path mapping from the constitution."""
        path = self.root_path / ".intent/knowledge/source_structure.yaml"
        data = load_config(path, "yaml")

        if not data:
            return self._infer_domains_from_directory_structure()

        structure = data.get("structure")
        if not structure:
            return self._infer_domains_from_directory_structure()

        return {
            Path(e["path"]).as_posix(): e["domain"]
            for e in structure
            if "path" in e and "domain" in e
        }

    def _infer_domains_from_directory_structure(self) -> Dict[str, str]:
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
                domain_name = item.name
                domain_path = item.relative_to(self.root_path)
                domain_map[domain_path.as_posix()] = domain_name

        log.info(
            f"   -> Inferred {len(domain_map)} domains from `src/` directory structure."
        )
        return domain_map

    def determine_domain(self, file_path: Path) -> str:
        """Determines the logical domain for a file path based on the longest matching prefix."""
        # This function receives a path that is already relative to the repo root.
        file_posix = file_path.as_posix()
        best_match = ""

        for domain_path in self.domain_map:
            if file_posix.startswith(domain_path) and len(domain_path) > len(
                best_match
            ):
                best_match = domain_path

        return self.domain_map.get(best_match, "unassigned")

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
