# src/features/maintenance/refactor_to_providers.py

"""
Constitutional Provider Refactoring Service

Automates migration from direct settings imports to provider pattern:
- IntentRepository for .intent/ access (Mind layer)
- FileProvider for other file reads
- Dependency injection for paths

This service implements automated refactoring with constitutional compliance.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from shared.logger import getLogger


logger = getLogger(__name__)


@dataclass
# ID: c40e19f4-3a89-4439-bf59-cf888ce03759
class SettingsUsagePattern:
    """Detected settings usage pattern in a file."""

    file_path: Path
    line_num: int
    pattern_type: str  # 'REPO_PATH', 'MIND', 'load', 'get_path', 'paths'
    code: str
    context: str  # 'class_init', 'function', 'module_level'


@dataclass
# ID: d460bca4-dda4-4952-b5a6-a1507877bf20
class RefactorStrategy:
    """Refactoring strategy determined for a file."""

    file_path: Path
    strategy_type: (
        str  # 'intent_repository', 'repo_path_param', 'manual_review', 'skip'
    )
    confidence: str  # 'high', 'medium', 'low'
    patterns: list[SettingsUsagePattern]
    changes_needed: list[str]  # Human-readable change descriptions


# ID: 515c2680-cdee-4c84-a7cd-d56ab59f1685
class ProviderRefactoringAnalyzer:
    """Analyzes files to determine provider refactoring strategy."""

    # Attributes that indicate IntentRepository usage
    INTENT_ATTRS: ClassVar[set[str]] = {"MIND", "get_path", "load", "paths"}

    # Simple path attributes
    PATH_ATTRS: ClassVar[set[str]] = {"REPO_PATH"}

    def __init__(self, repo_path: Path):
        self.repo_path = repo_path

    # ID: 69e4e24b-f2ac-42c0-b183-cd0c3cea95ed
    def analyze_file(self, file_path: Path) -> RefactorStrategy:
        """Analyze a file and determine refactoring strategy."""
        try:
            content = file_path.read_text()
            tree = ast.parse(content)
        except Exception as e:
            logger.debug("Cannot parse %s: %s", file_path, e)
            return RefactorStrategy(
                file_path=file_path,
                strategy_type="skip",
                confidence="high",
                patterns=[],
                changes_needed=[f"Parse error: {e}"],
            )

        # Find all settings usage
        patterns = self._find_settings_patterns(tree, content)

        if not patterns:
            return RefactorStrategy(
                file_path=file_path,
                strategy_type="skip",
                confidence="high",
                patterns=[],
                changes_needed=["No settings usage found"],
            )

        # Determine strategy based on patterns
        return self._determine_strategy(file_path, patterns)

    def _find_settings_patterns(
        self, tree: ast.Module, content: str
    ) -> list[SettingsUsagePattern]:
        """Find all settings.X usage patterns in the AST."""
        patterns = []
        lines = content.splitlines()

        for node in ast.walk(tree):
            # Check for settings.ATTRIBUTE access
            if isinstance(node, ast.Attribute):
                if isinstance(node.value, ast.Name) and node.value.id == "settings":
                    line_num = node.lineno
                    attr = node.attr
                    code = lines[line_num - 1] if line_num <= len(lines) else ""

                    patterns.append(
                        SettingsUsagePattern(
                            file_path=Path(),  # Set by caller
                            line_num=line_num,
                            pattern_type=attr,
                            code=code.strip(),
                            context=self._get_context(node, tree),
                        )
                    )

            # Check for settings.method() calls
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if (
                        isinstance(node.func.value, ast.Name)
                        and node.func.value.id == "settings"
                    ):
                        method = node.func.attr
                        if method in ["load", "get_path"]:
                            line_num = node.lineno
                            code = lines[line_num - 1] if line_num <= len(lines) else ""

                            patterns.append(
                                SettingsUsagePattern(
                                    file_path=Path(),
                                    line_num=line_num,
                                    pattern_type=method,
                                    code=code.strip(),
                                    context=self._get_context(node, tree),
                                )
                            )

        return patterns

    def _get_context(self, node: ast.AST, tree: ast.Module) -> str:
        """Determine if node is in __init__, function, or module level."""
        # Simple heuristic: check if we're inside __init__
        for parent_node in ast.walk(tree):
            if isinstance(parent_node, ast.FunctionDef):
                if parent_node.name == "__init__":
                    # Check if node is descendant of this function
                    for child in ast.walk(parent_node):
                        if child is node:
                            return "class_init"
                else:
                    for child in ast.walk(parent_node):
                        if child is node:
                            return "function"
        return "module_level"

    def _determine_strategy(
        self, file_path: Path, patterns: list[SettingsUsagePattern]
    ) -> RefactorStrategy:
        """Determine the appropriate refactoring strategy."""
        # Extract attributes used
        attrs_used = {p.pattern_type for p in patterns}

        # Set file_path on all patterns
        for p in patterns:
            p.file_path = file_path

        # Strategy 1: Uses .intent/ access → IntentRepository
        if attrs_used & self.INTENT_ATTRS:
            return RefactorStrategy(
                file_path=file_path,
                strategy_type="intent_repository",
                confidence="high",
                patterns=patterns,
                changes_needed=[
                    "Add IntentRepository parameter to __init__",
                    "Replace settings.MIND with intent_repo.root",
                    "Replace settings.load() with intent_repo.load_policy()",
                    "Remove settings import",
                ],
            )

        # Strategy 2: Only uses REPO_PATH → repo_path parameter
        if attrs_used == self.PATH_ATTRS:
            return RefactorStrategy(
                file_path=file_path,
                strategy_type="repo_path_param",
                confidence="high",
                patterns=patterns,
                changes_needed=[
                    "Add repo_path: Path parameter to __init__",
                    "Replace settings.REPO_PATH with self.repo_path",
                    "Remove settings import",
                ],
            )

        # Strategy 3: Mixed or complex usage → manual review
        return RefactorStrategy(
            file_path=file_path,
            strategy_type="manual_review",
            confidence="low",
            patterns=patterns,
            changes_needed=[
                f"Complex usage of settings attributes: {attrs_used}",
                "Requires manual review and refactoring",
            ],
        )


# ID: 0f5a2d06-9733-46f0-8b64-ca6ddf60f558
# ID: c9c08c1c-754e-4595-ad5c-932d150dc78e
async def analyze_layer_for_refactoring(repo_path: Path, layer: str) -> dict[str, Any]:
    """
    Analyze a layer (mind/will) for settings refactoring needs.

    Args:
        repo_path: Repository root path
        layer: Layer name ('mind' or 'will')

    Returns:
        Analysis results with statistics and file lists
    """
    layer_path = repo_path / "src" / layer
    if not layer_path.exists():
        return {"error": f"Layer {layer} not found at {layer_path}"}

    analyzer = ProviderRefactoringAnalyzer(repo_path)

    results = {
        "layer": layer,
        "analyzed": 0,
        "strategies": {
            "intent_repository": [],
            "repo_path_param": [],
            "manual_review": [],
            "skip": [],
        },
        "summary": {
            "intent_repository": 0,
            "repo_path_param": 0,
            "manual_review": 0,
            "skip": 0,
        },
    }

    # Analyze all Python files
    for py_file in layer_path.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue

        results["analyzed"] += 1

        strategy = analyzer.analyze_file(py_file)
        results["strategies"][strategy.strategy_type].append(
            {
                "file": str(py_file.relative_to(repo_path)),
                "confidence": strategy.confidence,
                "patterns_count": len(strategy.patterns),
                "changes_needed": strategy.changes_needed,
            }
        )
        results["summary"][strategy.strategy_type] += 1

    return results


# ID: 19919e6c-aca2-4115-89c0-b7464e675270
# ID: af2b6a8d-db1c-405a-b73b-8307bf382f8a
def generate_refactoring_report(analysis_results: dict[str, Any]) -> str:
    """Generate human-readable refactoring report."""
    lines = [
        "=" * 80,
        "CONSTITUTIONAL SETTINGS REFACTORING ANALYSIS",
        "=" * 80,
        "",
        f"Layer: {analysis_results['layer'].upper()}",
        f"Files analyzed: {analysis_results['analyzed']}",
        "",
    ]

    summary = analysis_results["summary"]
    automatable = summary["intent_repository"] + summary["repo_path_param"]

    lines.extend(
        [
            "SUMMARY:",
            f"  ✅ High-confidence (automatable): {automatable}",
            f"     - IntentRepository pattern: {summary['intent_repository']}",
            f"     - Repo path parameter: {summary['repo_path_param']}",
            f"  ⚠️  Manual review needed: {summary['manual_review']}",
            f"  ⏭️  No changes needed: {summary['skip']}",
            "",
        ]
    )

    # Detail sections
    for strategy_type, files in analysis_results["strategies"].items():
        if not files:
            continue

        lines.extend(
            [
                "=" * 80,
                f"{strategy_type.upper().replace('_', ' ')}",
                "=" * 80,
                "",
            ]
        )

        for file_info in files:
            lines.append(f"📄 {file_info['file']}")
            lines.append(f"   Confidence: {file_info['confidence']}")
            lines.append(f"   Patterns found: {file_info['patterns_count']}")
            lines.append("   Changes needed:")
            for change in file_info["changes_needed"]:
                lines.append(f"   - {change}")
            lines.append("")

    return "\n".join(lines)
