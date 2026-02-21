# src/body/analyzers/file_analyzer.py
# ID: 76d6ef2c-d42f-46f8-a52a-ddf5402eaf36
"""File Analyzer - Analyzes Python file structure and classifies type.

Constitutional Alignment:
- Phase: PARSE (Structural analysis and classification)
- Authority: CODE (Implementation of structural rules)
- Boundary: Respects repo_path via CoreContext (dependency injection required)

Purified (V2.3.0)
- Removed Will-layer DecisionTracer to satisfy architecture.layers.no_body_to_will.
  Rationale is now returned in metadata.
"""

from __future__ import annotations

import ast
import time
from typing import Any

from body.analyzers.base_analyzer import BaseAnalyzer
from shared.component_primitive import ComponentResult  # Component, ComponentPhase,
from shared.context import CoreContext
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: c9251530-0236-41a9-9630-b305f283277a
class FileAnalyzer(BaseAnalyzer):
    """Analyzes Python files to detect type and complexity.

    Determines if a file is a:
    - sqlalchemy_model: Requires integration fixtures.
    - async_module: Requires pytest-asyncio.
    - function_module / class_module: Requires standard unit testing.

    Constitutional requirements:
    - MUST be initialized with CoreContext containing valid git_service.
    - Body layer components do not access settings directly.
    """

    def __init__(self, context: CoreContext | None = None):
        """Initialize with context for governed path resolution."""
        self.context = context

    # ID: ddb4df7c-87db-40dd-91b1-1691cb0b8203
    async def execute(self, file_path: str, **kwargs) -> ComponentResult:
        """Analyze file structure and classify for downstream strategy selection."""
        start_time = time.time()

        # Constitutional boundary enforcement: Body requires proper context
        if not self.context or not getattr(self.context, "git_service", None):
            return ComponentResult(
                component_id=self.component_id,
                ok=False,
                data={
                    "error": (
                        "FileAnalyzer requires CoreContext with git_service. "
                        "Body layer components must not access settings directly."
                    )
                },
                phase=self.phase,
                confidence=0.0,
            )

        repo_root = self.context.git_service.repo_path
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

            analysis = self._analyze_ast(tree)
            file_type, confidence = self._classify_file(analysis)

            duration = time.time() - start_time

            # CONSTITUTIONAL FIX: Removed internal tracer call.
            # Return rationale and classification facts in metadata for the Agent to log.
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
                    "rationale": (
                        f"Classified {file_path} as {file_type} based on structural markers"
                    ),
                    "decision_context": {
                        "agent": "FileAnalyzer",
                        "decision_type": "file_classification",
                        "has_sqlalchemy": analysis["has_sqlalchemy"],
                        "has_async": analysis["has_async"],
                        "definitions": analysis["total_definitions"],
                    },
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
        facts: dict[str, Any] = {
            "has_sqlalchemy": False,
            "has_base_class": False,
            "has_mapped": False,
            "has_async": False,
            "class_count": 0,
            "function_count": 0,
            "async_function_count": 0,
        }

        for node in ast.walk(tree):
            # Check imports for framework usage
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "sqlalchemy" in alias.name:
                        facts["has_sqlalchemy"] = True

            elif isinstance(node, ast.ImportFrom):
                if node.module and "sqlalchemy" in node.module:
                    facts["has_sqlalchemy"] = True
                    if any("Mapped" in a.name for a in node.names):
                        facts["has_mapped"] = True

            # Count definitions
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

        # Categorize complexity
        if total > 15:
            facts["complexity"] = "high"
        elif total > 5:
            facts["complexity"] = "medium"
        else:
            facts["complexity"] = "low"

        return facts

    def _classify_file(self, analysis: dict[str, Any]) -> tuple[str, float]:
        """Classify file type based on collected facts.

        Returns:
            (file_type, confidence)
        """
        # SQLAlchemy model detection
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
