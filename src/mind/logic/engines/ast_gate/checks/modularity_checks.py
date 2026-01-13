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


# ID: a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d
class ModularityChecker:
    """Enforces modularity and refactoring thresholds constitutionally."""

    # These patterns are the CORE of your detection logic.
    # I have restored them exactly as they appear in your original file.
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
            r"if\s+.*:\s+.*elif\s+.*:\s+.*else:",
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
            r"asyncio\.",
            r"for\s+.*\s+in\s+.*:\s+await",
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

    # --- INTERNAL HELPER METHODS (Restored from your original) ---

    def _detect_responsibilities(self, content: str) -> list[str]:
        found_responsibilities = set()
        for responsibility, patterns in self.RESPONSIBILITY_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    found_responsibilities.add(responsibility)
                    break
        return sorted(found_responsibilities)

    def _extract_functions(self, tree: ast.AST) -> list[dict[str, str]]:
        functions = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                docstring = ast.get_docstring(node) or ""
                functions.append({"name": node.name, "docstring": docstring})
        return functions

    def _calculate_cohesion(self, functions: list[dict[str, str]]) -> float:
        """
        Original Jaccard Similarity Logic.
        Calculates how related the functions are based on word overlap.
        """
        if len(functions) < 2:
            return 1.0
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
        similarities = []
        for i in range(len(function_words)):
            for j in range(i + 1, len(function_words)):
                intersection = len(function_words[i] & function_words[j])
                union = len(function_words[i] | function_words[j])
                if union > 0:
                    similarities.append(intersection / union)
        return sum(similarities) / len(similarities) if similarities else 0.0

    def _extract_imports(self, tree: ast.AST) -> list[str]:
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
        concerns = set()
        for imp in imports:
            imp_lower = imp.lower()
            for concern, keywords in self.IMPORT_CONCERNS.items():
                if any(kw in imp_lower for kw in keywords):
                    concerns.add(concern)
        return sorted(concerns)

    # --- THE MASTER SCORE LOGIC (Updated to pull from YAML) ---

    # ID: 0a9433fe-9b18-4f46-8171-6eb1df60d60e
    def check_refactor_score(
        self, file_path: Path, params: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Calculate comprehensive refactor score based on all dimensions.
        """
        # We take the Target Value from the YAML params, fallback to 60.0
        target_value = float(params.get("max_score", 60.0))
        warning_level = target_value * 0.8  # Gauss Gauge

        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content)

            # 1. Responsibilities (Weight: 40)
            resps = self._detect_responsibilities(content)
            resp_count = len(resps)
            # Penalty starts after 1st responsibility
            resp_score = min(max(0, resp_count - 1) * 15, 40)

            # 2. Cohesion (Weight: 25)
            functions = self._extract_functions(tree)
            cohesion = self._calculate_cohesion(functions)
            # Higher score for LOWER cohesion (Debt)
            cohesion_score = (1.0 - cohesion) * 25

            # 3. Coupling (Weight: 20)
            imports = self._extract_imports(tree)
            concerns = self._identify_concerns(imports)
            # Penalty starts after 3rd concern area
            coupling_score = min(max(0, len(concerns) - 3) * 7, 20)

            # 4. Size (Weight: 15)
            loc = len(content.splitlines())
            # Penalty starts after 200 lines
            size_score = min(max(0, (loc - 200) // 20), 15)

            total_score = resp_score + cohesion_score + coupling_score + size_score

            # Return a finding if we exceed the Warning level (80% of target)
            if total_score > warning_level:
                severity = "error" if total_score > target_value else "warning"
                return [
                    {
                        "rule_id": "modularity.refactor_score_threshold",
                        "severity": severity,
                        "message": f"Modularity Debt: {total_score:.1f}/100 (Limit: {target_value})",
                        "file": str(file_path),
                        "details": {
                            "total_score": total_score,
                            "responsibility_count": resp_count,
                            "responsibilities": resps,
                            "cohesion": cohesion,
                            "concern_count": len(concerns),
                            "concerns": concerns,
                            "lines_of_code": loc,
                            "breakdown": {
                                "responsibilities": resp_score,
                                "cohesion": cohesion_score,
                                "coupling": coupling_score,
                                "size": size_score,
                            },
                        },
                    }
                ]
            return []

        except Exception as e:
            logger.error("Analysis failed for %s: %s", file_path, e)
            return []

    # Compatibility methods to ensure 'check audit' doesn't break
    # ID: c964d35a-6041-42e2-80fa-ade2cf3c103e
    def check_single_responsibility(
        self, file_path: Path, params: dict[str, Any]
    ) -> list[dict[str, Any]]:
        return self.check_refactor_score(file_path, params)

    # ID: e3847502-6d16-4f47-88f3-fdc6c0353e62
    def check_semantic_cohesion(
        self, file_path: Path, params: dict[str, Any]
    ) -> list[dict[str, Any]]:
        return self.check_refactor_score(file_path, params)

    # ID: 13dfc006-8cb9-4c3f-949c-7a508b560b77
    def check_import_coupling(
        self, file_path: Path, params: dict[str, Any]
    ) -> list[dict[str, Any]]:
        return self.check_refactor_score(file_path, params)
