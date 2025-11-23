# src/features/self_healing/test_context_analyzer.py

"""
Analyzes target modules to build rich context for test generation.

This service gathers comprehensive context about a module to help the LLM
understand what to test and how. It prevents misunderstandings like testing
'HTML headers' when the module is about 'file headers'.
"""

from __future__ import annotations

import ast
import subprocess
from dataclasses import dataclass
from typing import Any

from shared.config import settings
from shared.logger import getLogger

logger = getLogger(__name__)


@dataclass
# ID: 8dde3ec5-ce2c-4486-b6d7-7751ceaabfd0
class ModuleContext:
    """Rich context about a module for test generation."""

    module_path: str
    module_name: str
    import_path: str
    source_code: str
    module_docstring: str | None
    classes: list[dict[str, Any]]
    functions: list[dict[str, Any]]
    imports: list[str]
    dependencies: list[str]
    current_coverage: float
    uncovered_lines: list[int]
    uncovered_functions: list[str]
    similar_test_files: list[dict[str, Any]]
    external_deps: list[str]
    filesystem_usage: bool
    database_usage: bool
    network_usage: bool

    # ID: 02560995-d66d-493d-8896-138a623a8304
    def to_prompt_context(self) -> str:
        """Convert to formatted context for LLM prompt."""
        lines = []
        lines.append("# MODULE CONTEXT")
        lines.append(f"\n## Module: {self.module_path}")
        lines.append(f"Import as: `{self.import_path}`")
        if self.module_docstring:
            lines.append("\n## Purpose")
            lines.append(self.module_docstring)
        lines.append("\n## Coverage Status")
        lines.append(f"Current Coverage: {self.current_coverage:.1f}%")
        if self.uncovered_functions:
            lines.append(f"Uncovered Functions ({len(self.uncovered_functions)}):")
            for func in self.uncovered_functions[:10]:
                lines.append(f"  - {func}")
        lines.append("\n## Module Structure")
        if self.classes:
            lines.append(f"Classes ({len(self.classes)}):")
            for cls in self.classes:
                lines.append(
                    f"  - {cls['name']}: {cls.get('docstring', 'No description')[:80]}"
                )
        if self.functions:
            lines.append(f"Functions ({len(self.functions)}):")
            for func in self.functions:
                lines.append(
                    f"  - {func['name']}: {func.get('docstring', 'No description')[:80]}"
                )
        lines.append("\n## Dependencies to Mock")
        if self.external_deps:
            lines.append("External dependencies that MUST be mocked:")
            for dep in self.external_deps:
                lines.append(f"  - {dep}")
        if self.filesystem_usage:
            lines.append(
                "⚠️  This module uses filesystem operations - use tmp_path fixture!"
            )
        if self.database_usage:
            lines.append("⚠️  This module uses database - mock get_session()!")
        if self.network_usage:
            lines.append("⚠️  This module uses network - mock httpx requests!")
        if self.similar_test_files:
            lines.append("\n## Example Test Patterns from Similar Modules")
            for example in self.similar_test_files[:2]:
                lines.append(f"\n### Example from {example['file']}")
                lines.append("```python")
                lines.append(example["snippet"])
                lines.append("```")
        return "\n".join(lines)


# ID: ef6215e4-e04e-47bf-ac4c-a3efa9131ad0
class TestContextAnalyzer:
    """Analyzes modules to gather rich context for test generation."""

    def __init__(self):
        self.repo_root = settings.REPO_PATH

    # ID: 76a78ffa-390c-46dd-a271-065ece4576dc
    async def analyze_module(self, module_path: str) -> ModuleContext:
        """
        Perform comprehensive analysis of a module.

        Args:
            module_path: Path to the module (e.g., "src/core/prompt_pipeline.py")

        Returns:
            Rich context about the module
        """
        logger.info(f"Analyzing module: {module_path}")
        full_path = self.repo_root / module_path
        if not full_path.exists():
            raise FileNotFoundError(f"Module not found: {full_path}")
        source_code = full_path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source_code)
        except SyntaxError as e:
            logger.error(f"Failed to parse {module_path}: {e}")
            raise
        module_name = full_path.stem
        import_path = (
            module_path.replace("src/", "").replace(".py", "").replace("/", ".")
        )
        module_docstring = ast.get_docstring(tree)
        classes = self._extract_classes(tree)
        functions = self._extract_functions(tree)
        imports = self._extract_imports(tree)
        dependencies = self._analyze_dependencies(imports)
        external_deps = self._identify_external_deps(imports)
        filesystem_usage = self._detect_filesystem_usage(source_code)
        database_usage = self._detect_database_usage(source_code)
        network_usage = self._detect_network_usage(source_code)
        coverage_info = self._get_coverage_for_file(module_path)
        similar_tests = self._find_similar_test_examples(
            module_name, classes, functions
        )
        return ModuleContext(
            module_path=module_path,
            module_name=module_name,
            import_path=import_path,
            source_code=source_code,
            module_docstring=module_docstring,
            classes=classes,
            functions=functions,
            imports=imports,
            dependencies=dependencies,
            current_coverage=coverage_info["coverage"],
            uncovered_lines=coverage_info["uncovered_lines"],
            uncovered_functions=coverage_info["uncovered_functions"],
            similar_test_files=similar_tests,
            external_deps=external_deps,
            filesystem_usage=filesystem_usage,
            database_usage=database_usage,
            network_usage=network_usage,
        )

    def _extract_classes(self, tree: ast.AST) -> list[dict[str, Any]]:
        """Extract all class definitions with their methods."""
        classes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                methods = []
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        methods.append(
                            {
                                "name": item.name,
                                "docstring": ast.get_docstring(item),
                                "is_private": item.name.startswith("_"),
                                "args": [arg.arg for arg in item.args.args],
                            }
                        )
                classes.append(
                    {
                        "name": node.name,
                        "docstring": ast.get_docstring(node),
                        "methods": methods,
                        "bases": [self._get_name(base) for base in node.bases],
                    }
                )
        return classes

    def _extract_functions(self, tree: ast.AST) -> list[dict[str, Any]]:
        """Extract top-level functions (not methods)."""
        functions = []
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                functions.append(
                    {
                        "name": node.name,
                        "docstring": ast.get_docstring(node),
                        "is_private": node.name.startswith("_"),
                        "is_async": isinstance(node, ast.AsyncFunctionDef),
                        "args": [arg.arg for arg in node.args.args],
                    }
                )
        return functions

    def _extract_imports(self, tree: ast.AST) -> list[str]:
        """Extract all import statements."""
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
        return list(set(imports))

    def _analyze_dependencies(self, imports: list[str]) -> list[str]:
        """Identify internal project dependencies."""
        internal_deps = []
        for imp in imports:
            if any(
                imp.startswith(pkg)
                for pkg in ["core", "features", "shared", "services", "cli"]
            ):
                internal_deps.append(imp)
        return internal_deps

    def _identify_external_deps(self, imports: list[str]) -> list[str]:
        """Identify external dependencies that need mocking."""
        mock_required = []
        external_patterns = [
            "httpx",
            "requests",
            "sqlalchemy",
            "psycopg2",
            "redis",
            "boto3",
            "anthropic",
            "openai",
        ]
        for imp in imports:
            for pattern in external_patterns:
                if pattern in imp.lower():
                    mock_required.append(imp)
                    break
        return list(set(mock_required))

    def _detect_filesystem_usage(self, source_code: str) -> bool:
        """Detect if module uses filesystem operations."""
        fs_indicators = [
            "Path(",
            "open(",
            ".read_text",
            ".write_text",
            ".mkdir(",
            ".exists(",
            "os.path",
            "shutil.",
        ]
        return any(indicator in source_code for indicator in fs_indicators)

    def _detect_database_usage(self, source_code: str) -> bool:
        """Detect if module uses database operations."""
        db_indicators = [
            "get_session",
            "Session(",
            "query(",
            "select(",
            "insert(",
            "update(",
            "delete(",
            "sessionmaker",
        ]
        return any(indicator in source_code for indicator in db_indicators)

    def _detect_network_usage(self, source_code: str) -> bool:
        """Detect if module makes network requests."""
        network_indicators = [
            "httpx.",
            "requests.",
            "AsyncClient",
            ".get(",
            ".post(",
            "urllib.",
        ]
        return any(indicator in source_code for indicator in network_indicators)

    def _get_coverage_for_file(self, module_path: str) -> dict[str, Any]:
        """Get coverage information for specific file."""
        try:
            result = subprocess.run(
                [
                    "pytest",
                    "--cov=" + str(self.repo_root / "src"),
                    "--cov-report=json",
                    "-q",
                ],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=30,
            )
            import json

            coverage_file = self.repo_root / "coverage.json"
            if coverage_file.exists():
                data = json.loads(coverage_file.read_text())
                file_key = str(self.repo_root / module_path)
                if file_key in data.get("files", {}):
                    file_data = data["files"][file_key]
                    uncovered = file_data.get("missing_lines", [])
                    summary = file_data.get("summary", {})
                    total = summary.get("num_statements", 1)
                    covered = summary.get("covered_lines", 0)
                    coverage = covered / total * 100 if total > 0 else 0
                    return {
                        "coverage": coverage,
                        "uncovered_lines": uncovered,
                        "uncovered_functions": self._map_lines_to_functions(
                            module_path, uncovered
                        ),
                    }
        except Exception as e:
            logger.warning(f"Could not get coverage for {module_path}: {e}")
        return {"coverage": 0.0, "uncovered_lines": [], "uncovered_functions": []}

    def _map_lines_to_functions(
        self, module_path: str, uncovered_lines: list[int]
    ) -> list[str]:
        """Map uncovered line numbers to function names."""
        try:
            full_path = self.repo_root / module_path
            source = full_path.read_text(encoding="utf-8")
            tree = ast.parse(source)
            uncovered_funcs = []
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    func_start = node.lineno
                    func_end = node.end_lineno or func_start
                    if any(func_start <= line <= func_end for line in uncovered_lines):
                        uncovered_funcs.append(node.name)
            return list(set(uncovered_funcs))
        except Exception as e:
            logger.warning(f"Could not map lines to functions: {e}")
            return []

    def _find_similar_test_examples(
        self, module_name: str, classes: list[dict], functions: list[dict]
    ) -> list[dict[str, Any]]:
        """Find existing test files with similar patterns."""
        examples = []
        tests_dir = self.repo_root / "tests"
        if not tests_dir.exists():
            return examples
        for test_file in tests_dir.rglob("test_*.py"):
            try:
                content = test_file.read_text(encoding="utf-8")
                similarity_score = 0
                for cls in classes:
                    if cls["name"].lower() in content.lower():
                        similarity_score += 2
                for func in functions:
                    if func["name"] in content:
                        similarity_score += 1
                if similarity_score > 0:
                    snippet = self._extract_test_snippet(content)
                    examples.append(
                        {
                            "file": str(test_file.relative_to(self.repo_root)),
                            "similarity": similarity_score,
                            "snippet": snippet,
                        }
                    )
            except Exception as e:
                logger.debug(f"Could not analyze {test_file}: {e}")
                continue
        examples.sort(key=lambda x: x["similarity"], reverse=True)
        return examples[:3]

    def _extract_test_snippet(self, content: str, max_lines: int = 20) -> str:
        """Extract a representative test snippet."""
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if line.strip().startswith("def test_"):
                snippet_lines = []
                indent_level = len(line) - len(line.lstrip())
                for j in range(i, min(i + max_lines, len(lines))):
                    test_line = lines[j]
                    if j > i and test_line.strip().startswith("def "):
                        break
                    snippet_lines.append(test_line)
                return "\n".join(snippet_lines)
        return "\n".join(lines[:max_lines])

    def _get_name(self, node: ast.AST) -> str:
        """Safely get name from AST node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_name(node.value)}.{node.attr}"
        return str(node)
