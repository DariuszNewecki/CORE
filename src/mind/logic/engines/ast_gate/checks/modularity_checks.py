# src/mind/logic/engines/ast_gate/checks/modularity_checks.py
"""
Modularity checks - enforces UNIX philosophy and refactoring thresholds.

Constitutional Rules:
- modularity.single_responsibility: max 2 responsibilities per file
- modularity.semantic_cohesion: min 0.70 cohesion score
- modularity.import_coupling: max 3 concern areas
- modularity.refactor_score_threshold: max score 60
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any, ClassVar

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: a1b2c3d4-e5f6-7a8b-9c0d-e1f2a3b4c5d6
class ModularityChecker:
    """Enforces modularity and refactoring thresholds constitutionally."""

    # Responsibility patterns
    RESPONSIBILITY_PATTERNS: ClassVar[dict[str, list[str]]] = {
        "data_access": [
            r"session\.",
            r"\.query\(",
            r"\.filter\(",
            r"\.join\(",
            r"SELECT\s+",
            r"INSERT\s+",
            r"UPDATE\s+",
            r"DELETE\s+",
        ],
        "business_logic": [
            r"def\s+calculate_",
            r"def\s+compute_",
            r"def\s+process_",
            r"def\s+transform_",
            r"if\s+.*:\s+.*elif\s+.*:\s+.*else:",  # Complex conditionals
        ],
        "presentation": [
            r"console\.print",
            r"rich\.",
            r"typer\.",
            r"Table\(",
            r"Panel\(",
            r"\.render\(",
        ],
        "orchestration": [
            r"await\s+.*\.execute\(",
            r"\.run\(",
            r"for\s+.*\s+in\s+.*:\s+await",
            r"asyncio\.",
        ],
        "validation": [
            r"def\s+validate_",
            r"def\s+check_",
            r"if\s+not\s+.*:\s+raise",
            r"assert\s+",
        ],
        "io_operations": [
            r"\.read_text\(",
            r"\.write_text\(",
            r"open\(",
            r"Path\(",
            r"\.exists\(",
        ],
        "network": [
            r"requests\.",
            r"httpx\.",
            r"fetch\(",
            r"\.get\(",
            r"\.post\(",
        ],
        "testing": [
            r"def\s+test_",
            r"pytest\.",
            r"mock\.",
            r"assert\s+.*==",
        ],
    }

    # Import concern mapping
    IMPORT_CONCERNS: ClassVar[dict[str, list[str]]] = {
        "database": ["sqlalchemy", "psycopg2", "session", "query", "orm"],
        "web": ["fastapi", "requests", "httpx", "aiohttp", "flask"],
        "testing": ["pytest", "unittest", "mock", "hypothesis"],
        "ml": ["sklearn", "torch", "transformers", "numpy", "pandas"],
        "cli": ["typer", "click", "argparse", "rich"],
        "file_io": ["pathlib", "json", "yaml", "toml", "pickle"],
        "async": ["asyncio", "aiofiles", "trio"],
        "logging": ["logging", "logger", "getLogger"],
    }

    def __init__(self):
        self.cognitive_service = None
        self.embeddings_cache: dict[str, list[float]] = {}

    # ID: 28b23367-f133-429a-b018-91000db62002
    def check_single_responsibility(
        self, file_path: Path, params: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Check if file has too many responsibilities.

        Args:
            file_path: Path to file to check
            params: {'max_responsibilities': 2}

        Returns:
            List of findings (empty if compliant)
        """
        max_responsibilities = params.get("max_responsibilities", 2)

        try:
            content = file_path.read_text(encoding="utf-8")
            responsibilities = self._detect_responsibilities(content)

            if len(responsibilities) > max_responsibilities:
                return [
                    {
                        "rule_id": "modularity.single_responsibility",
                        "severity": "warning",
                        "message": f"File has {len(responsibilities)} responsibilities (max: {max_responsibilities}): {', '.join(responsibilities)}",
                        "file": str(file_path),
                        "line": 1,
                        "details": {"responsibilities": responsibilities},
                    }
                ]

            return []

        except Exception as e:
            logger.error(
                "Failed to check single responsibility for %s: %s", file_path, e
            )
            return []

    # ID: 22575d12-1a27-46cf-bd5f-f60b9673b9d6
    def check_semantic_cohesion(
        self, file_path: Path, params: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Check if functions in file are semantically cohesive.

        Args:
            file_path: Path to file to check
            params: {'min_cohesion': 0.70}

        Returns:
            List of findings (empty if compliant)
        """
        min_cohesion = params.get("min_cohesion", 0.70)

        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content)

            functions = self._extract_functions(tree)

            if len(functions) < 2:
                # Can't measure cohesion with < 2 functions
                return []

            cohesion_score = self._calculate_cohesion(functions)

            if cohesion_score < min_cohesion:
                return [
                    {
                        "rule_id": "modularity.semantic_cohesion",
                        "severity": "warning",
                        "message": f"Low semantic cohesion: {cohesion_score:.2f} (min: {min_cohesion:.2f}). Functions may not belong together.",
                        "file": str(file_path),
                        "line": 1,
                        "details": {
                            "cohesion_score": cohesion_score,
                            "function_count": len(functions),
                        },
                    }
                ]

            return []

        except Exception as e:
            logger.debug("Failed to check semantic cohesion for %s: %s", file_path, e)
            return []

    # ID: b01a56f7-09ff-43b2-9602-237009b850e2
    def check_import_coupling(
        self, file_path: Path, params: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Check if file touches too many concern areas.

        Args:
            file_path: Path to file to check
            params: {'max_concerns': 3}

        Returns:
            List of findings (empty if compliant)
        """
        max_concerns = params.get("max_concerns", 3)

        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content)

            imports = self._extract_imports(tree)
            concerns = self._identify_concerns(imports)

            if len(concerns) > max_concerns:
                return [
                    {
                        "rule_id": "modularity.import_coupling",
                        "severity": "warning",
                        "message": f"High coupling: touches {len(concerns)} concern areas (max: {max_concerns}): {', '.join(concerns)}",
                        "file": str(file_path),
                        "line": 1,
                        "details": {"concerns": concerns, "imports": imports[:10]},
                    }
                ]

            return []

        except Exception as e:
            logger.error("Failed to check import coupling for %s: %s", file_path, e)
            return []

    # ID: 0a9433fe-9b18-4f46-8171-6eb1df60d60e
    def check_refactor_score(
        self, file_path: Path, params: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Calculate comprehensive refactor score.

        Args:
            file_path: Path to file to check
            params: {'max_score': 60}

        Returns:
            List of findings (empty if compliant)
        """
        max_score = params.get("max_score", 60)

        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content)

            # Calculate components
            responsibilities = self._detect_responsibilities(content)
            resp_score = min(len(responsibilities) * 15, 40)

            functions = self._extract_functions(tree)
            cohesion = (
                self._calculate_cohesion(functions) if len(functions) >= 2 else 1.0
            )
            cohesion_score = (1 - cohesion) * 25

            imports = self._extract_imports(tree)
            concerns = self._identify_concerns(imports)
            coupling_score = min(len(concerns) * 5, 20)

            loc = len(content.splitlines())
            size_score = min((loc - 200) / 40, 5) if loc > 200 else 0

            total_score = resp_score + cohesion_score + coupling_score + size_score

            if total_score > max_score:
                return [
                    {
                        "rule_id": "modularity.refactor_score_threshold",
                        "severity": "warning",
                        "message": f"Refactor score: {total_score:.1f}/100 (threshold: {max_score}). Consider refactoring.",
                        "file": str(file_path),
                        "line": 1,
                        "details": {
                            "total_score": total_score,
                            "breakdown": {
                                "responsibilities": resp_score,
                                "cohesion": cohesion_score,
                                "coupling": coupling_score,
                                "size": size_score,
                            },
                            "responsibility_count": len(responsibilities),
                            "responsibilities": responsibilities,
                            "cohesion": cohesion,
                            "concern_count": len(concerns),
                            "concerns": concerns,
                            "lines_of_code": loc,
                        },
                    }
                ]

            return []

        except Exception as e:
            logger.error("Failed to check refactor score for %s: %s", file_path, e)
            return []

    def _detect_responsibilities(self, content: str) -> list[str]:
        """Detect responsibilities in code content."""
        found_responsibilities = set()

        for responsibility, patterns in self.RESPONSIBILITY_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    found_responsibilities.add(responsibility)
                    break

        return sorted(found_responsibilities)

    def _extract_functions(self, tree: ast.AST) -> list[dict[str, str]]:
        """Extract function definitions with docstrings."""
        functions = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                docstring = ast.get_docstring(node) or ""
                functions.append({"name": node.name, "docstring": docstring})

        return functions

    def _calculate_cohesion(self, functions: list[dict[str, str]]) -> float:
        """
        Calculate semantic cohesion between functions.

        For now, uses simple heuristic. In future, integrate with
        cognitive_service for real embeddings.
        """
        if len(functions) < 2:
            return 1.0

        # Heuristic: check for common word stems in function names/docstrings
        all_words = set()
        function_words = []

        for func in functions:
            words = set(
                re.findall(
                    r"\w+", func["name"].lower() + " " + func["docstring"].lower()
                )
            )
            function_words.append(words)
            all_words.update(words)

        # Calculate Jaccard similarity between function word sets
        similarities = []
        for i in range(len(function_words)):
            for j in range(i + 1, len(function_words)):
                intersection = len(function_words[i] & function_words[j])
                union = len(function_words[i] | function_words[j])
                if union > 0:
                    similarities.append(intersection / union)

        return sum(similarities) / len(similarities) if similarities else 0.0

    def _extract_imports(self, tree: ast.AST) -> list[str]:
        """Extract import statements."""
        imports = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)

        return imports

    def _identify_concerns(self, imports: list[str]) -> list[str]:
        """Map imports to concern areas."""
        concerns = set()

        for imp in imports:
            imp_lower = imp.lower()
            for concern, keywords in self.IMPORT_CONCERNS.items():
                if any(kw in imp_lower for kw in keywords):
                    concerns.add(concern)

        return sorted(concerns)
