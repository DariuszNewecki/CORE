# src/system/tools/ast_analyzer.py
"""
Parses Python source files to extract function and class symbols while detecting entry points and domain mappings.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Dict, List

from shared.logger import getLogger
from system.tools.config.builder_config import BuilderConfig
from system.tools.domain_mapper import DomainMapper
from system.tools.entry_point_detector import EntryPointDetector
from system.tools.models import FunctionInfo
from system.tools.symbol_processor import ProcessingContext, SymbolProcessor

log = getLogger(__name__)


# CAPABILITY: tooling.ast.analyze
class ASTAnalyzer:
    """Handles AST parsing and symbol extraction from Python files."""

    # CAPABILITY: tooling.ast.initialize
    def __init__(self, config: BuilderConfig):
        """Initializes the ASTAnalyzer with the builder configuration."""
        self.config = config
        self.entry_point_detector = EntryPointDetector(config)
        self.symbol_processor = SymbolProcessor()
        self.files_scanned = 0
        self.files_failed = 0

    # CAPABILITY: tooling.ast.analyze_files
    def analyze_files(
        self, files: List[Path], domain_mapper: DomainMapper
    ) -> Dict[str, FunctionInfo]:
        """Analyze multiple files and return all discovered symbols."""
        symbols = {}

        for file_path in files:
            file_symbols = self.analyze_file(file_path, domain_mapper)
            symbols.update(file_symbols)

        log.info(f"Scanned {self.files_scanned} files ({self.files_failed} failed)")
        return symbols

    # CAPABILITY: tooling.ast.analyze_file
    def analyze_file(
        self, filepath: Path, domain_mapper: DomainMapper
    ) -> Dict[str, FunctionInfo]:
        """Analyze a single Python file and extract all symbols."""
        try:
            content = filepath.read_text(encoding="utf-8")
            source_lines = content.splitlines()
            tree = ast.parse(content, filename=str(filepath))

            # Detect FastAPI app and main block calls
            self.entry_point_detector.detect_fastapi_app_name(tree)
            main_block_calls = self.entry_point_detector.detect_main_block_calls(tree)
            self.entry_point_detector.update_cli_entry_points(main_block_calls)

            # Create processing context
            context = ProcessingContext(
                filepath=filepath,
                root_path=self.config.root_path,
                source_lines=source_lines,
                domain_mapper=domain_mapper,
                entry_point_detector=self.entry_point_detector,
            )

            # Process all nodes in the AST
            symbols = {}
            # Instead of complex parent tracking, process top-level nodes and recurse for methods
            for node in tree.body:
                if isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                ):
                    symbol_info = self.symbol_processor.process_node(node, context)
                    if symbol_info:
                        symbols[symbol_info.key] = symbol_info

                        # Process methods if this is a class
                        if symbol_info.is_class:
                            method_symbols = self._process_class_methods(
                                node, context, symbol_info.key
                            )
                            symbols.update(method_symbols)

            self.files_scanned += 1
            return symbols

        except UnicodeDecodeError as e:
            log.error(f"Encoding error scanning {filepath}: {e}")
            self.files_failed += 1
            return {}
        except Exception as e:
            log.error(f"Error scanning {filepath}: {e}")
            self.files_failed += 1
            return {}

    # CAPABILITY: tooling.ast.process_class_methods
    def _process_class_methods(
        self, class_node: ast.ClassDef, context: ProcessingContext, parent_key: str
    ) -> Dict[str, FunctionInfo]:
        """Process all methods within a class."""
        methods = {}

        # Create new context for methods with parent key
        method_context = ProcessingContext(
            filepath=context.filepath,
            root_path=context.root_path,
            source_lines=context.source_lines,
            domain_mapper=context.domain_mapper,
            entry_point_detector=context.entry_point_detector,
            parent_key=parent_key,
        )

        for child_node in class_node.body:
            if isinstance(child_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                method_info = self.symbol_processor.process_node(
                    child_node, method_context
                )
                if method_info:
                    methods[method_info.key] = method_info

        return methods
