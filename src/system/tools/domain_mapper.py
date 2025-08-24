# src/system/tools/domain_mapper.py
"""
Maps file paths and symbols to their logical domains and responsible agents.
"""

from __future__ import annotations

"""
Maps file paths and symbols to their logical domains and responsible agents.
"""
# src/system/tools/domain_mapper.py
from pathlib import Path

from system.tools.config.builder_config import BuilderConfig


class DomainMapper:
    """Handles domain determination for files and symbols."""

    def __init__(self, config: BuilderConfig):
        """Initializes the DomainMapper with the builder configuration."""
        self.domain_map = config.domain_map
        self.root_path = config.root_path

    def get_domain_for_file(self, file_path: Path) -> str:
        """Determine the logical domain for a file path based on longest matching prefix."""
        file_posix = file_path.as_posix()
        best_match = max(
            (path for path in self.domain_map if file_posix.startswith(path)),
            key=len,
            default="",
        )
        return self.domain_map.get(best_match, "unassigned")

    def infer_agent_from_path(self, relative_path: Path) -> str:
        """Infer the most likely responsible agent based on keywords in the file path."""
        path_str = str(relative_path).lower()

        if "planner" in path_str:
            return "planner_agent"
        if "generator" in path_str:
            return "generator_agent"
        if any(keyword in path_str for keyword in ["validator", "guard", "audit"]):
            return "validator_agent"
        if "core" in path_str:
            return "core_agent"
        if "tool" in path_str:
            return "tooling_agent"

        return "generic_agent"
