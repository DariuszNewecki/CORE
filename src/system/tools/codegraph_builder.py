# src/system/tools/codegraph_builder.py
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from filelock import FileLock

from shared.logger import getLogger
from system.tools.ast_analyzer import ASTAnalyzer
from system.tools.config.builder_config import BuilderConfig
from system.tools.domain_mapper import DomainMapper
from system.tools.file_scanner import FileScanner
from system.tools.pattern_matcher import PatternMatcher

log = getLogger(__name__)


class ProjectStructureError(Exception):
    """Custom exception for when the project's root cannot be determined."""

    pass


def find_project_root(start_path: Path) -> Path:
    """Traverse upward from a starting path to find the project root, marked by 'pyproject.toml'."""
    current_path = start_path.resolve()
    while current_path != current_path.parent:
        if (current_path / "pyproject.toml").exists():
            return current_path
        current_path = current_path.parent
    raise ProjectStructureError("Could not find 'pyproject.toml'.")


# CAPABILITY: manifest_updating
class KnowledgeGraphBuilder:
    """
    Builds a comprehensive JSON representation of the project's code structure and relationships.

    This is the main orchestrator that coordinates file scanning, AST analysis, domain mapping,
    and pattern matching to generate a complete knowledge graph of the codebase.
    """

    def __init__(self, root_path: Path, config: Optional[BuilderConfig] = None):
        """Initialize the builder with configuration and component dependencies."""
        self.root_path = root_path.resolve()
        self.config = config or BuilderConfig.from_project(root_path)

        # Initialize component dependencies
        self.file_scanner = FileScanner(self.config)
        self.ast_analyzer = ASTAnalyzer(self.config)
        self.domain_mapper = DomainMapper(self.config)
        self.pattern_matcher = PatternMatcher(self.config.patterns, root_path)

    def build(self) -> Dict[str, Any]:
        """
        Orchestrate the full knowledge graph generation process.

        Returns:
            Dict containing the complete knowledge graph with metadata and symbols.
        """
        log.info(f"Building knowledge graph for directory: {self.config.src_root}")

        # Step 1: Find all Python files to analyze
        files = self.file_scanner.find_python_files()
        if not files:
            log.warning("No Python files found to analyze")
            return self._build_empty_output()

        # Step 2: Analyze all files and extract symbols
        symbols = self.ast_analyzer.analyze_files(files, self.domain_mapper)

        # Step 3: Apply declarative patterns to enhance symbol information
        log.info("Applying declarative patterns...")
        self.pattern_matcher.apply_patterns(symbols)

        # Step 4: Build final output
        return self._build_output(symbols)

    def _build_output(self, symbols: Dict[str, Any]) -> Dict[str, Any]:
        """Build the final JSON output structure."""
        # Convert FunctionInfo objects to dictionaries, filtering out None values
        serializable_symbols = {
            key: asdict(
                info, dict_factory=lambda x: {k: v for (k, v) in x if v is not None}
            )
            for key, info in symbols.items()
        }

        # Sort call lists for consistent output
        for data in serializable_symbols.values():
            data["calls"] = sorted(list(data["calls"]))

        return {
            "schema_version": "2.0.0",
            "metadata": {
                "files_scanned": self.ast_analyzer.files_scanned,
                "total_symbols": len(symbols),
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            },
            "symbols": serializable_symbols,
        }

    def _build_empty_output(self) -> Dict[str, Any]:
        """Build output structure when no files are found."""
        return {
            "schema_version": "2.0.0",
            "metadata": {
                "files_scanned": 0,
                "total_symbols": 0,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            },
            "symbols": {},
        }


def main():
    """CLI entry point to run the knowledge graph builder and save the output."""
    load_dotenv()
    try:
        root = find_project_root(Path.cwd())
        builder = KnowledgeGraphBuilder(root)
        graph = builder.build()

        # Save output
        out_path = root / ".intent/knowledge/knowledge_graph.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)

        with FileLock(str(out_path) + ".lock"):
            out_path.write_text(json.dumps(graph, indent=2))

        log.info(
            f"✅ Knowledge graph generated! "
            f"Scanned {graph['metadata']['files_scanned']} files, "
            f"found {graph['metadata']['total_symbols']} symbols."
        )
        log.info(f"   -> Saved to {out_path}")

    except Exception as e:
        log.error(f"An error occurred: {e}", exc_info=True)


if __name__ == "__main__":
    main()
