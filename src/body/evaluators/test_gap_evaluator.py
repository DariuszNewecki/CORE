# src/body/evaluators/test_gap_evaluator.py
"""
TestGapEvaluator — AUDIT phase gap analysis for autonomous test generation.

Reads the source file and existing test file (if any) via AST, computes which
public symbols are untested, and returns a structured GapReport. No LLM calls,
no file writes, no database access.

Implements ADR-133 D1/D2: symbol-gap detection as a pure AUDIT component,
consumed by TestRemediatorWorker before proposal creation to convert file-level
remediation into per-symbol proposals.
"""

from __future__ import annotations

import ast
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from body.evaluators.base_evaluator import BaseEvaluator
from shared.component_primitive import ComponentResult
from shared.logger import getLogger


logger = getLogger(__name__)

_DUNDER_SKIP: frozenset[str] = frozenset(
    {
        "__init__",
        "__repr__",
        "__str__",
        "__eq__",
        "__hash__",
        "__lt__",
        "__le__",
        "__gt__",
        "__ge__",
        "__len__",
        "__bool__",
        "__enter__",
        "__exit__",
        "__aenter__",
        "__aexit__",
        "__iter__",
        "__next__",
        "__contains__",
        "__getitem__",
        "__setitem__",
        "__delitem__",
    }
)


@dataclass
# ID: 8fa4a2a4-5a8f-4f43-8091-451aabe4757b
class SymbolGap:
    name: str
    kind: str
    signature: str
    tested: bool = False


@dataclass
# ID: 1fa65a8d-6e46-4667-b47c-04fca8ab14ee
class GapReport:
    source_file: str
    gaps: list[SymbolGap]
    already_covered: list[SymbolGap]
    test_file: str
    test_file_exists: bool


# ID: 1a149618-5420-49fa-8cbc-96c4f1dcf232
class TestGapEvaluator(BaseEvaluator):
    """
    AUDIT phase evaluator: identifies untested public symbols in a source file.

    Reads source AST for public module-level functions and classes. Reads
    existing test file AST (when present) for test_<name> functions to
    determine which symbols already have coverage. Returns the gap set for
    TestRemediatorWorker to convert into per-symbol build.test_for_symbol
    proposals (ADR-133 D1/D2/D4).
    """

    def __init__(self, repo_root: Path, context: Any = None) -> None:
        super().__init__(context)
        self._repo_root = repo_root

    @property
    # ID: b4a2dadf-88fa-431c-98d5-9f90fc6e33f8
    def component_id(self) -> str:
        return "test_gap_evaluator"

    # ID: 7fd5f2e8-f17c-4773-bded-3cf98588d278
    async def execute(self, source_file: str, **kwargs: Any) -> ComponentResult:
        """
        Evaluate which public symbols in source_file lack test coverage.

        Args:
            source_file: repo-relative path (e.g. "src/body/foo.py").

        Returns:
            ComponentResult with data containing "gaps" (untested) and
            "already_covered" (tested) lists, each a list of SymbolGap dicts.
        """
        from shared.infrastructure.intent.test_coverage_paths import source_to_test_path

        start = time.time()

        try:
            test_file = source_to_test_path(source_file)
        except ValueError as e:
            return await self._create_result(
                ok=False,
                data={"error": str(e), "source_file": source_file},
                confidence=0.0,
                duration=time.time() - start,
                rationale=f"Cannot derive test path for {source_file}: {e}",
            )

        source_path = self._repo_root / source_file
        if not source_path.exists():
            return await self._create_result(
                ok=False,
                data={"error": f"Source file not found: {source_file}"},
                confidence=0.0,
                duration=time.time() - start,
                rationale="Source file does not exist on disk",
            )

        try:
            symbols = _extract_public_symbols(source_path)
        except SyntaxError as e:
            return await self._create_result(
                ok=False,
                data={
                    "error": f"Syntax error in source: {e}",
                    "source_file": source_file,
                },
                confidence=0.0,
                duration=time.time() - start,
                rationale="Source file has a syntax error — cannot extract symbols",
            )

        test_path = self._repo_root / test_file
        test_file_exists = test_path.exists()
        tested_names: set[str] = set()
        if test_file_exists:
            try:
                tested_names = _extract_tested_names(test_path)
            except SyntaxError:
                logger.warning(
                    "TestGapEvaluator: cannot parse existing test file %s — "
                    "treating all symbols as untested",
                    test_file,
                )

        gaps: list[SymbolGap] = []
        covered: list[SymbolGap] = []
        for sym in symbols:
            if sym.name in tested_names:
                sym.tested = True
                covered.append(sym)
            else:
                gaps.append(sym)

        logger.info(
            "TestGapEvaluator: %s — %d gaps, %d covered out of %d symbols",
            source_file,
            len(gaps),
            len(covered),
            len(symbols),
        )

        return await self._create_result(
            ok=True,
            data={
                "source_file": source_file,
                "test_file": test_file,
                "test_file_exists": test_file_exists,
                "gaps": [asdict(g) for g in gaps],
                "already_covered": [asdict(c) for c in covered],
                "gap_count": len(gaps),
                "covered_count": len(covered),
            },
            confidence=1.0,
            duration=time.time() - start,
            rationale=(
                f"{len(gaps)} untested / {len(covered)} covered "
                f"out of {len(symbols)} public symbols in {source_file}"
            ),
        )


# ID: a6b5bc75-c1b5-4cc2-b2b5-ceed9349d070
def _extract_public_symbols(source_path: Path) -> list[SymbolGap]:
    """Extract module-level public functions and classes from source_path via AST."""
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(source_path))
    symbols: list[SymbolGap] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                symbols.append(
                    SymbolGap(
                        name=node.name,
                        kind="function",
                        signature=_format_signature(node),
                    )
                )
        elif isinstance(node, ast.ClassDef):
            if not node.name.startswith("_"):
                symbols.append(
                    SymbolGap(
                        name=node.name,
                        kind="class",
                        signature=f"class {node.name}",
                    )
                )
    return symbols


# ID: 26137180-53a9-4360-8535-a221d09ae847
def _extract_tested_names(test_path: Path) -> set[str]:
    """Return the set of symbol names implied by test_<name> functions in test_path."""
    source = test_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(test_path))
    tested: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("test_"):
                tested.add(node.name[5:])
    return tested


def _format_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args = [arg.arg for arg in node.args.args]
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    return f"{prefix} {node.name}({', '.join(args)})"
