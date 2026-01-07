# src/body/analyzers/symbol_extractor.py

"""
Symbol Extractor - Extracts testable symbols from Python files.

Constitutional Alignment:
- Phase: PARSE (Structural metadata extraction)
- Authority: CODE (Implementation of structural analysis)
- SSOT: Aligns symbol keys with core.symbols DB schema (filepath::qualname)
- Tracing: Mandatory DecisionTracer integration
"""

from __future__ import annotations

import ast
import time
from dataclasses import dataclass

from shared.component_primitive import Component, ComponentPhase, ComponentResult
from shared.config import settings
from shared.context import CoreContext
from shared.logger import getLogger
from will.orchestration.decision_tracer import DecisionTracer


logger = getLogger(__name__)


@dataclass
# ID: c9728355-9313-4ab3-9258-813393a0b195
class SymbolMetadata:
    """
    Structured metadata for a testable symbol.
    Aligned with the Knowledge Graph (SSOT) schema.
    """

    name: str
    qualname: str
    symbol_path: str  # Format: path/to/file.py::QualName
    type: str  # 'function', 'async_function', 'class'
    line_number: int
    docstring: str | None
    is_public: bool
    complexity: str  # 'low', 'medium', 'high'
    parameters: list[str]
    decorators: list[str]


# ID: 45a15e98-cf61-4f87-b2b4-c023fb783654
class SymbolExtractor(Component):
    """
    Extracts testable symbols (functions and classes) from Python files.

    Constitutional Filters:
    - Skips private symbols (starting with _)
    - Skips explicit test files (test_*.py)
    - Skips dunder magic methods (except those requiring specific coverage)
    """

    def __init__(self, context: CoreContext | None = None):
        self.context = context
        self.tracer = DecisionTracer()

    @property
    # ID: 88898be4-86f2-4bf4-ba81-06a34759d3f3
    def phase(self) -> ComponentPhase:
        return ComponentPhase.PARSE

    # ID: a98b1814-002c-4deb-aeb9-dadc7039ac60
    async def execute(
        self, file_path: str, include_private: bool = False, **kwargs
    ) -> ComponentResult:
        """
        Analyze a file and extract symbol metadata.
        """
        start_time = time.time()

        if self.context and self.context.git_service:
            repo_root = self.context.git_service.repo_path
        else:
            repo_root = settings.REPO_PATH

        abs_path = (repo_root / file_path).resolve()

        if not abs_path.exists():
            return ComponentResult(
                component_id=self.component_id,
                ok=False,
                data={"error": f"File not found: {file_path}"},
                phase=self.phase,
                confidence=0.0,
            )

        # Constitutional Guard: Identify if this is already a test file
        if abs_path.name.startswith("test_") or abs_path.name.endswith("_test.py"):
            return ComponentResult(
                component_id=self.component_id,
                ok=True,
                data={"symbols": [], "skipped": True, "reason": "is_test_file"},
                phase=self.phase,
                confidence=1.0,
            )

        try:
            source_code = abs_path.read_text(encoding="utf-8")
            tree = ast.parse(source_code)

            # Perform extraction
            extracted_symbols = self._extract_symbols(tree, file_path, include_private)

            # Tally metrics
            public_count = sum(1 for s in extracted_symbols if s.is_public)
            class_count = sum(1 for s in extracted_symbols if s.type == "class")

            # Mandatory Decision Tracing
            self.tracer.record(
                agent="SymbolExtractor",
                decision_type="metadata_extraction",
                rationale=f"Discovered structural symbols in {file_path}",
                chosen_action="return_symbol_list",
                context={
                    "file": file_path,
                    "total_found": len(extracted_symbols),
                    "public_api_count": public_count,
                },
            )

            duration = time.time() - start_time
            return ComponentResult(
                component_id=self.component_id,
                ok=True,
                data={
                    "symbols": [s.__dict__ for s in extracted_symbols],
                    "total_count": len(extracted_symbols),
                    "public_count": public_count,
                    "class_count": class_count,
                    "function_count": len(extracted_symbols) - class_count,
                },
                phase=self.phase,
                confidence=1.0,
                next_suggested="test_strategist",
                duration_sec=duration,
                metadata={"file_path": file_path},
            )

        except SyntaxError as e:
            return ComponentResult(
                component_id=self.component_id,
                ok=False,
                data={"error": f"Syntax error in {file_path}: {e}"},
                phase=self.phase,
                confidence=0.0,
            )
        except Exception as e:
            logger.error("SymbolExtractor failure: %s", e, exc_info=True)
            return ComponentResult(
                component_id=self.component_id,
                ok=False,
                data={"error": str(e)},
                phase=self.phase,
                confidence=0.0,
            )

    def _extract_symbols(
        self, tree: ast.AST, rel_path: str, include_private: bool
    ) -> list[SymbolMetadata]:
        symbols = []
        # Walk only top-level to avoid internal closures/nested funcs unless classes
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                meta = self._build_class_meta(node, rel_path)
                if include_private or meta.is_public:
                    symbols.append(meta)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                meta = self._build_function_meta(node, rel_path)
                if include_private or meta.is_public:
                    symbols.append(meta)
        return symbols

    def _build_class_meta(self, node: ast.ClassDef, rel_path: str) -> SymbolMetadata:
        is_public = not node.name.startswith("_")
        doc = ast.get_docstring(node)

        # SSOT Mapping
        symbol_path = f"{rel_path}::{node.name}"

        # Structural Complexity Assessment
        methods = [
            n
            for n in node.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        complexity = (
            "high" if len(methods) > 10 else "medium" if len(methods) > 3 else "low"
        )

        return SymbolMetadata(
            name=node.name,
            qualname=node.name,
            symbol_path=symbol_path,
            type="class",
            line_number=node.lineno,
            docstring=doc,
            is_public=is_public,
            complexity=complexity,
            parameters=[],
            decorators=[self._get_dec_name(d) for d in node.decorator_list],
        )

    def _build_function_meta(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, rel_path: str
    ) -> SymbolMetadata:
        is_public = not node.name.startswith("_")
        doc = ast.get_docstring(node)

        # SSOT Mapping
        symbol_path = f"{rel_path}::{node.name}"

        # Structural Complexity Assessment
        body_len = len(node.body)
        complexity = "high" if body_len > 25 else "medium" if body_len > 10 else "low"

        func_type = (
            "async_function" if isinstance(node, ast.AsyncFunctionDef) else "function"
        )

        return SymbolMetadata(
            name=node.name,
            qualname=node.name,
            symbol_path=symbol_path,
            type=func_type,
            line_number=node.lineno,
            docstring=doc,
            is_public=is_public,
            complexity=complexity,
            parameters=[a.arg for a in node.args.args],
            decorators=[self._get_dec_name(d) for d in node.decorator_list],
        )

    def _get_dec_name(self, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        if isinstance(node, ast.Call):
            return self._get_dec_name(node.func)
        return "unknown_decorator"


SymbolInfo = SymbolMetadata
