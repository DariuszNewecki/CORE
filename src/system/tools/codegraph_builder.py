# src/system/tools/codegraph_builder.py
"""
Main knowledge graph builder orchestrating all components.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from shared.config_loader import load_config
from shared.logger import getLogger
from system.tools.domain_mapper import DomainMapper
from system.tools.entry_point_detector import EntryPointDetector
from system.tools.file_scanner import FileScanner
from system.tools.graph_serializer import GraphSerializer
from system.tools.pattern_matcher import PatternMatcher
from system.tools.project_structure import (
    ProjectStructureError,
    find_project_root,
    get_cli_entry_points,
    get_python_files,
)

log = getLogger(__name__)


class KnowledgeGraphBuilder:
    """Builds a comprehensive JSON representation of the project's code structure and relationships."""

    def __init__(self, root_path: Path, exclude_patterns: Optional[List[str]] = None):
        """Initializes the builder, loading patterns and project configuration."""
        self.root_path = root_path.resolve()
        self.src_root = self.root_path / "src"
        self.exclude_patterns = exclude_patterns or [
            "venv",
            ".venv",
            "__pycache__",
            ".git",
            "tests",
            "work",
        ]
        self.files_scanned = 0
        self.files_failed = 0

        # Initialize components
        cli_entry_points = get_cli_entry_points(self.root_path)
        self.domain_mapper = DomainMapper(self.root_path)
        self.entry_point_detector = EntryPointDetector(self.root_path, cli_entry_points)
        self.file_scanner = FileScanner(self.domain_mapper, self.entry_point_detector)
        self.pattern_matcher = PatternMatcher(self._load_patterns(), self.root_path)

    def _load_patterns(self) -> List[Dict]:
        """Loads entry point detection patterns from the intent file."""
        patterns_path = self.root_path / ".intent/knowledge/entry_point_patterns.yaml"
        if not patterns_path.exists():
            log.warning("entry_point_patterns.yaml not found.")
            return []
        config = load_config(patterns_path, "yaml")
        return config.get("patterns", []) if config else []

    def build(self) -> Dict[str, Any]:
        """Orchestrates the full knowledge graph generation process."""
        log.info(f"Building knowledge graph for directory: {self.src_root}")

        py_files = get_python_files(self.src_root, self.exclude_patterns)
        log.info(f"Found {len(py_files)} Python files to scan in src/")

        # Scan all files
        for pyfile in py_files:
            if self.file_scanner.scan_file(pyfile):
                self.files_scanned += 1
            else:
                self.files_failed += 1

        log.info(
            f"Scanned {self.files_scanned} files ({self.files_failed} failed). "
            f"Applying declarative patterns..."
        )

        # Apply patterns to enhance the function data
        self.pattern_matcher.apply_patterns(self.file_scanner.functions)

        # Build and return the serialized graph
        return GraphSerializer.build_graph_data(
            self.file_scanner.functions, self.files_scanned
        )


def main():
    """CLI entry point to run the knowledge graph builder and save the output."""
    load_dotenv()
    try:
        # Find project root robustly
        try:
            root = find_project_root(Path.cwd())
        except ProjectStructureError:
            log.warning(
                "Could not find pyproject.toml, using current directory as root. "
                "This may cause issues."
            )
            root = Path.cwd()

        # Build the knowledge graph
        builder = KnowledgeGraphBuilder(root)
        graph = builder.build()

        # Save to file
        out_path = root / ".intent/knowledge/knowledge_graph.json"
        GraphSerializer.save_to_file(graph, out_path)

    except Exception as e:
        log.error(f"An error occurred: {e}", exc_info=True)


if __name__ == "__main__":
    main()
