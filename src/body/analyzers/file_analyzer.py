# src/body/analyzers/file_analyzer.py

"""
File Analyzer - Analyzes Python file structure and classifies type.

Constitutional Alignment:
- Phase: PARSE (Structural analysis and classification)
- Authority: CODE (Implementation of structural rules)
- Tracing: Mandatory DecisionTracer integration for classification verdicts
- Boundary: Respects repo_path via CoreContext
"""

from __future__ import annotations

import ast
import time
from typing import Any

from shared.component_primitive import Component, ComponentPhase, ComponentResult
from shared.config import settings
from shared.context import CoreContext
from shared.logger import getLogger
from will.orchestration.decision_tracer import DecisionTracer


logger = getLogger(__name__)


# ID: 76d6ef2c-d42f-46f8-a52a-ddf5402eaf36
class FileAnalyzer(Component):
    """
    Analyzes Python files to detect type and complexity.

    Determines if a file is a:
    - sqlalchemy_model: Requires integration fixtures.
    - async_module: Requires pytest-asyncio.
    - function_module/class_module: Requires standard unit testing.
    """

    def __init__(self, context: CoreContext | None = None):
        """
        Initialize with optional context for governed path resolution.
        """
        self.context = context
        self.tracer = DecisionTracer()

    @property
    # ID: f380c886-12d6-4630-a4ae-e100f2e931fe
    def phase(self) -> ComponentPhase:
        return ComponentPhase.PARSE

    # ID: ddb4df7c-87db-40dd-91b1-1691cb0b8203
    async def execute(self, file_path: str, **kwargs) -> ComponentResult:
        """
        Analyze file structure and classify for downstream strategy selection.
        """
        start_time = time.time()

        # Governed path resolution
        if self.context and self.context.git_service:
            repo_root = self.context.git_service.repo_path
        else:
            repo_root = settings.REPO_PATH  # Fallback to SSOT settings

        abs_path = (repo_root / file_path).resolve()

        if not abs_path.exists():
            return ComponentResult(
                component_id=self.component_id,
                ok=False,
                data={"error": f"File not found: {file_path}"},
                phase=self.phase,
                confidence=0.0,
            )

        try:
            code = abs_path.read_text(encoding="utf-8")
            tree = ast.parse(code)

            # Extract structural facts
            analysis = self._analyze_ast(tree)
            file_type, confidence = self._classify_file(analysis)

            # Mandatory Decision Tracing (Constitutional Rule: autonomy.tracing.mandatory)
            self.tracer.record(
                agent="FileAnalyzer",
                decision_type="file_classification",
                rationale=f"Classified {file_path} based on structural markers",
                chosen_action=file_type,
                context={
                    "has_sqlalchemy": analysis["has_sqlalchemy"],
                    "has_async": analysis["has_async"],
                    "definitions": analysis["total_definitions"],
                },
                confidence=confidence,
            )

            duration = time.time() - start_time
            return ComponentResult(
                component_id=self.component_id,
                ok=True,
                data={
                    "file_type": file_type,
                    "has_sqlalchemy": analysis["has_sqlalchemy"],
                    "has_async": analysis["has_async"],
                    "class_count": analysis["class_count"],
                    "function_count": analysis["function_count"],
                    "complexity": analysis["complexity"],
                },
                phase=self.phase,
                confidence=confidence,
                next_suggested="symbol_extractor",
                duration_sec=duration,
                metadata={
                    "file_path": file_path,
                    "line_count": len(code.splitlines()),
                    "total_definitions": analysis["total_definitions"],
                },
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
            logger.error("FileAnalyzer failed for %s: %s", file_path, e, exc_info=True)
            return ComponentResult(
                component_id=self.component_id,
                ok=False,
                data={"error": str(e)},
                phase=self.phase,
                confidence=0.0,
            )

    def _analyze_ast(self, tree: ast.AST) -> dict[str, Any]:
        """Extract structural facts from AST."""
        facts = {
            "has_sqlalchemy": False,
            "has_base_class": False,
            "has_mapped": False,
            "has_async": False,
            "class_count": 0,
            "function_count": 0,
            "async_function_count": 0,
        }

        for node in ast.walk(tree):
            # Check Imports for Framework usage
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "sqlalchemy" in alias.name:
                        facts["has_sqlalchemy"] = True
            elif isinstance(node, ast.ImportFrom):
                if node.module and "sqlalchemy" in node.module:
                    facts["has_sqlalchemy"] = True
                    if any("Mapped" in a.name for a in node.names):
                        facts["has_mapped"] = True

            # Count Definitions
            elif isinstance(node, ast.ClassDef):
                facts["class_count"] += 1
                for base in node.bases:
                    if isinstance(base, ast.Name) and base.id == "Base":
                        facts["has_base_class"] = True
            elif isinstance(node, ast.FunctionDef):
                facts["function_count"] += 1
            elif isinstance(node, ast.AsyncFunctionDef):
                facts["async_function_count"] += 1
                facts["has_async"] = True

        total = (
            facts["class_count"]
            + facts["function_count"]
            + facts["async_function_count"]
        )
        facts["total_definitions"] = total

        # Categorize Complexity
        if total > 15:
            facts["complexity"] = "high"
        elif total > 5:
            facts["complexity"] = "medium"
        else:
            facts["complexity"] = "low"

        return facts

    def _classify_file(self, analysis: dict[str, Any]) -> tuple[str, float]:
        """
        Classify file type based on collected facts.
        Returns (file_type, confidence).
        """
        # SQLAlchemy Model detection
        if analysis["has_sqlalchemy"] and (
            analysis["has_base_class"] or analysis["has_mapped"]
        ):
            return ("sqlalchemy_model", 0.95)

        # Async module detection
        if analysis["has_async"] and analysis["async_function_count"] > 1:
            return ("async_module", 0.90)

        # Class-heavy logic
        if analysis["class_count"] > 0 and analysis["function_count"] == 0:
            return ("class_module", 0.85)

        # Function-heavy logic
        if analysis["function_count"] > 0 and analysis["class_count"] == 0:
            return ("function_module", 0.85)

        return ("mixed_module", 0.60)
