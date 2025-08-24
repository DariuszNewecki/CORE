# src/system/tools/symbol_processor.py
"""
Processes AST nodes (functions, classes) into structured FunctionInfo objects with metadata and domain context.
"""

from __future__ import annotations

# src/system/tools/symbol_processor.py
import ast
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from system.tools.ast_utils import (
    calculate_structural_hash,
    detect_docstring,
    extract_base_classes,
    extract_function_parameters,
    parse_metadata_comment,
)
from system.tools.ast_visitor import FunctionCallVisitor
from system.tools.domain_mapper import DomainMapper
from system.tools.entry_point_detector import EntryPointDetector
from system.tools.models import FunctionInfo


@dataclass
class ProcessingContext:
    """Context information needed for processing AST nodes."""

    filepath: Path
    root_path: Path
    source_lines: List[str]
    domain_mapper: DomainMapper
    entry_point_detector: EntryPointDetector
    parent_key: Optional[str] = None


class SymbolProcessor:
    """Processes individual AST nodes into FunctionInfo objects."""

    def process_node(
        self, node: ast.AST, context: ProcessingContext
    ) -> Optional[FunctionInfo]:
        """Process a single AST node into a FunctionInfo object."""
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return None

        # Calculate structural hash
        structural_hash = calculate_structural_hash(node)

        # Extract function calls
        visitor = FunctionCallVisitor()
        visitor.visit(node)

        # Build unique key
        key = (
            f"{context.filepath.relative_to(context.root_path).as_posix()}::{node.name}"
        )

        # Extract docstring
        docstring = detect_docstring(node)

        # Determine domain and agent
        relative_path = context.filepath.relative_to(context.root_path)
        domain = context.domain_mapper.get_domain_for_file(relative_path)
        agent = context.domain_mapper.infer_agent_from_path(relative_path)

        # Determine if this is a class
        is_class = isinstance(node, ast.ClassDef)

        # Extract class-specific information
        base_classes = extract_base_classes(node) if is_class else []

        # Extract function parameters (not applicable to classes)
        parameters = [] if is_class else extract_function_parameters(node)

        # Detect entry points (not applicable to classes)
        entry_point_type = (
            None
            if is_class
            else context.entry_point_detector.get_entry_point_type(node)
        )

        # Parse metadata comments
        capability = parse_metadata_comment(node, context.source_lines).get(
            "capability", "unassigned"
        )

        # Generate intent description
        intent = self._generate_intent(docstring, domain)

        return FunctionInfo(
            key=key,
            name=node.name,
            type=node.__class__.__name__,
            file=relative_path.as_posix(),
            calls=visitor.calls,
            line_number=node.lineno,
            is_async=isinstance(node, ast.AsyncFunctionDef),
            docstring=docstring,
            parameters=parameters,
            entry_point_type=entry_point_type,
            domain=domain,
            agent=agent,
            capability=capability,
            intent=intent,
            last_updated=datetime.now(timezone.utc).isoformat(),
            is_class=is_class,
            base_classes=base_classes,
            parent_class_key=context.parent_key,
            structural_hash=structural_hash,
        )

    def _generate_intent(self, docstring: Optional[str], domain: str) -> str:
        """Generate an intent description from docstring or domain."""
        if docstring:
            return docstring.split("\n")[0].strip()
        return f"Provides functionality for the {domain} domain."
