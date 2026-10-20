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

import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from body.evaluators.base_evaluator import BaseEvaluator
from shared.component_primitive import ComponentResult
from shared.infrastructure.intent.test_coverage_paths import source_to_test_path
from shared.logger import getLogger
from shared.utils.public_symbols import (
    extract_public_symbols,
    leaf_name_counts,
    name_key,
    symbol_is_tested,
    tested_symbol_names,
)


logger = getLogger(__name__)


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

    Reads source AST for public module-level functions, classes, and class
    methods (ADR-133 D2). Reads existing test file AST (when present) for
    test_<name> functions and TestClassName.test_<method> methods to determine
    which symbols already have coverage. Returns the gap set for
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

        tested_keys = {name_key(name) for name in tested_names}
        leaf_counts = leaf_name_counts([sym.name for sym in symbols])
        gaps: list[SymbolGap] = []
        covered: list[SymbolGap] = []
        for sym in symbols:
            if symbol_is_tested(sym.name, tested_keys, leaf_counts):
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
    """Public module-level functions, classes and class methods, via AST.

    The predicate is ``shared.utils.public_symbols.extract_public_symbols``
    — the same one the coverage scan uses to exempt modules with no public
    symbols (ADR-133 D2; governor ruling 2026-10-03), so the two cannot
    diverge. This wraps each result as an untested ``SymbolGap``.
    """
    return [
        SymbolGap(name=s.name, kind=s.kind, signature=s.signature)
        for s in extract_public_symbols(source_path)
    ]


def _extract_tested_names(test_path: Path) -> set[str]:
    """Symbol names covered by test_path (``tested_symbol_names``)."""
    return tested_symbol_names(test_path)
