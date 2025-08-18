# src/system/tools/domain_mapper.py
from pathlib import Path
from typing import Dict

# Corrected import to use the project's custom, test-aware logger
from shared.config_loader import load_config
from shared.logger import getLogger

# Configure logging for detailed CI diagnostics
# Using getLogger to integrate with your existing logger setup
log = getLogger(__name__)


class DomainMapper:
    """Maps file paths to their corresponding domains based on directory structure."""

    def __init__(self, root_path: Path):
        """Initialize the domain mapper with the root path of the project."""
        original_root = root_path
        self.root_path = Path(root_path).resolve()

        # INSTRUMENTATION
        log.debug(f"DomainMapper.__init__ - Original root_path input: {original_root}")
        log.debug(f"DomainMapper.__init__ - Final resolved root_path: {self.root_path}")

        self.domain_map_relative: Dict[Path, str] = self._load_domain_map()
        self.sorted_domain_paths = sorted(
            self.domain_map_relative.keys(), key=lambda p: len(p.parts), reverse=True
        )

    def _load_domain_map(self) -> Dict[Path, str]:
        """Load domain mappings from source_structure.yaml."""
        config_path = self.root_path / ".intent" / "knowledge" / "source_structure.yaml"

        try:
            data = load_config(config_path, "yaml")
        except Exception as e:
            log.warning(f"Could not load domain configuration from {config_path}: {e}")
            return {}

        structure = data.get("structure", [])
        if not isinstance(structure, list):
            log.warning("source_structure.yaml is missing a 'structure' list.")
            return {}

        domain_map = {}
        for entry in structure:
            if isinstance(entry, dict) and "path" in entry and "domain" in entry:
                relative_path = Path(entry["path"])
                domain_map[relative_path] = entry["domain"]

        # INSTRUMENTATION
        log.debug(
            f"DomainMapper._load_domain_map - Loaded {len(domain_map)} mappings: {domain_map}"
        )
        return domain_map

    def determine_domain(self, file_path_relative: Path) -> str:
        """Determine the domain for a file given its relative path from root."""
        # INSTRUMENTATION
        log.debug(
            f"determine_domain - Input file_path_relative: '{file_path_relative}' (type: {type(file_path_relative)})"
        )

        if not isinstance(file_path_relative, Path):
            file_path_relative = Path(file_path_relative)

        if file_path_relative.is_absolute():
            try:
                file_path_relative = file_path_relative.relative_to(self.root_path)
            except ValueError:
                log.warning(
                    f"Cannot make {file_path_relative} relative to {self.root_path}"
                )
                return "unassigned"

        # INSTRUMENTATION
        log.debug(
            f"determine_domain - Starting domain matching loop for: '{file_path_relative}'"
        )
        log.debug(
            f"determine_domain - Available domain paths: {self.sorted_domain_paths}"
        )

        for domain_path in self.sorted_domain_paths:
            # INSTRUMENTATION
            log.debug(
                f"determine_domain - ITERATION: Comparing '{file_path_relative}' against '{domain_path}'"
            )
            try:
                # Use is_relative_to for a more robust check in Python 3.9+
                if file_path_relative.is_relative_to(domain_path):
                    domain = self.domain_map_relative[domain_path]
                    log.debug(
                        f"determine_domain - MATCH FOUND: '{file_path_relative}' belongs to domain '{domain}'"
                    )
                    return domain
            except AttributeError:  # Fallback for older Python versions if needed
                if str(file_path_relative).startswith(str(domain_path)):
                    domain = self.domain_map_relative[domain_path]
                    log.debug(
                        f"determine_domain - MATCH FOUND: '{file_path_relative}' belongs to domain '{domain}'"
                    )
                    return domain

            log.debug("determine_domain - NO MATCH on this iteration.")
            continue

        log.debug(
            f"determine_domain - NO MATCH FOUND for '{file_path_relative}'. Returning 'unassigned'."
        )
        return "unassigned"

    def infer_agent_from_path(self, relative_path: Path) -> str:
        # ... (rest of the file is unchanged) ...
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
