# src/system/tools/symbol_processor.py
"""
Processes AST nodes (functions, classes) into structured FunctionInfo objects with metadata and domain context.
# CAPABILITY: symbol_processing
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from shared.ast_utility import (  # Import shared utilities
    FunctionCallVisitor,
    calculate_structural_hash,
    extract_base_classes,
    extract_docstring,
    extract_parameters,
    parse_metadata_comment,
)
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

        # Use shared utilities for AST processing
        structural_hash = calculate_structural_hash(node)

        visitor = FunctionCallVisitor()
        visitor.visit(node)

        # Build unique key
        key = (
            f"{context.filepath.relative_to(context.root_path).as_posix()}::{node.name}"
        )

        # Extract docstring using shared utility
        docstring = extract_docstring(node)

        # Determine domain and agent
        relative_path = context.filepath.relative_to(context.root_path)
        domain = context.domain_mapper.get_domain_for_file(relative_path)
        agent = context.domain_mapper.infer_agent_from_path(relative_path)

        # Determine if this is a class
        is_class = isinstance(node, ast.ClassDef)

        # Extract class-specific information using shared utility
        base_classes = extract_base_classes(node) if is_class else []

        # Extract function parameters (not applicable to classes) using shared utility
        parameters = [] if is_class else extract_parameters(node)

        # Detect entry points (not applicable to classes)
        entry_point_type = (
            None
            if is_class
            else context.entry_point_detector.get_entry_point_type(node)
        )

        # Parse metadata comments using shared utility
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
