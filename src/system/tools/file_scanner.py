# src/system/tools/file_scanner.py
"""
Scans individual Python files and extracts symbol information.
"""
import ast
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from shared.logger import getLogger
from system.tools.ast_utils import (
    calculate_structural_hash,
    detect_docstring,
    extract_base_classes,
    parse_metadata_comment,
)
from system.tools.ast_visitor import FunctionCallVisitor
from system.tools.domain_mapper import DomainMapper
from system.tools.entry_point_detector import EntryPointDetector
from system.tools.models import FunctionInfo

log = getLogger(__name__)


class FileScanner:
    """Scans Python files and extracts symbol information."""

    def __init__(
        self, domain_mapper: DomainMapper, entry_point_detector: EntryPointDetector
    ):
        """Initializes the scanner with its required helper components."""
        self.domain_mapper = domain_mapper
        self.entry_point_detector = entry_point_detector
        self.functions: Dict[str, FunctionInfo] = {}

    def scan_file(self, filepath: Path) -> bool:
        """Scans a single Python file, parsing its AST to extract all symbols."""
        try:
            content = filepath.read_text(encoding="utf-8")
            source_lines = content.splitlines()
            tree = ast.parse(content, filename=str(filepath))

            # Detect entry points and update detector state
            main_block_entries = self.entry_point_detector.detect_in_tree(tree)
            self.entry_point_detector.cli_entry_points.update(main_block_entries)

            # Process all function and class definitions in the file
            for node in ast.walk(tree):
                if isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                ):
                    self.process_symbol_node(node, filepath, source_lines)

            return True

        except UnicodeDecodeError as e:
            log.error(f"Encoding error scanning {filepath}: {e}")
            return False
        except Exception as e:
            log.error(f"Error scanning {filepath}: {e}")
            return False

    def process_symbol_node(
        self,
        node: ast.AST,
        filepath: Path,
        source_lines: list[str],
        parent_key: Optional[str] = None,
    ) -> Optional[str]:
        """Extracts and stores metadata from a single function or class AST node."""
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return None

        # Calculate structural hash
        structural_hash = calculate_structural_hash(node)

        # Extract function calls
        visitor = FunctionCallVisitor()
        visitor.visit(node)

        # Build function info
        key = f"{filepath.relative_to(self.domain_mapper.root_path).as_posix()}::{node.name}"
        doc = detect_docstring(node)
        domain = self.domain_mapper.determine_domain(
            filepath.relative_to(self.domain_mapper.root_path)
        )
        is_class = isinstance(node, ast.ClassDef)

        func_info = FunctionInfo(
            key=key,
            name=node.name,
            type=node.__class__.__name__,
            file=filepath.relative_to(self.domain_mapper.root_path).as_posix(),
            calls=visitor.calls,
            line_number=node.lineno,
            is_async=isinstance(node, ast.AsyncFunctionDef),
            docstring=doc,
            parameters=(
                [arg.arg for arg in node.args.args] if hasattr(node, "args") else []
            ),
            entry_point_type=(
                self.entry_point_detector.get_entry_point_type(node)
                if not is_class
                else None
            ),
            domain=domain,
            agent=self.domain_mapper.infer_agent_from_path(
                filepath.relative_to(self.domain_mapper.root_path)
            ),
            capability=parse_metadata_comment(node, source_lines).get(
                "capability", "unassigned"
            ),
            intent=(
                doc.split("\n")[0].strip()
                if doc
                else f"Provides functionality for the {domain} domain."
            ),
            last_updated=datetime.now(timezone.utc).isoformat(),
            is_class=is_class,
            base_classes=extract_base_classes(node) if is_class else [],
            parent_class_key=parent_key,
            structural_hash=structural_hash,
        )

        self.functions[key] = func_info

        # Process nested methods for classes
        if is_class:
            for child_node in node.body:
                if isinstance(child_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self.process_symbol_node(child_node, filepath, source_lines, key)

        return key
