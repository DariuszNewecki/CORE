# src/features/self_healing/coverage_analyzer.py

"""
Analyzes codebase coverage and module structure.

Provides coverage measurement and module complexity analysis
to support intelligent test prioritization.
"""

from __future__ import annotations

import ast
import json
import subprocess
from pathlib import Path
from typing import Any

# REFACTORED: Removed direct settings import
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 2b075104-ab91-4ea3-931b-a9be87d56799
class CoverageAnalyzer:
    """
    Analyzes test coverage and module structure for prioritization.
    """

    def __init__(self, repo_path: Path) -> None:
        self.repo_path = repo_path

    # ID: 168e0d67-a382-48a5-9dd5-79eeb9656cfa
    def get_module_coverage(self) -> dict[str, float]:
        """
        Gets current coverage percentage for each module.

        Returns:
            Dict mapping file paths to coverage percentages
        """
        try:
            subprocess.run(
                ["poetry", "run", "pytest", "--cov=src", "--cov-report=json", "-q"],
                cwd=self.repo_path,
                capture_output=True,
                timeout=120,
            )
            coverage_json = self.repo_path / "coverage.json"
            if coverage_json.exists():
                data = json.loads(coverage_json.read_text())
                module_coverage = {}
                for file_path, file_data in data.get("files", {}).items():
                    summary = file_data.get("summary", {})
                    percent = summary.get("percent_covered", 0)
                    module_coverage[file_path] = round(percent, 2)
                return module_coverage
        except Exception as e:
            logger.debug("Could not get module coverage: %s", e)
        return {}

    # ID: 12e50464-4e37-48a6-a738-5def4ee46de1
    def analyze_codebase(self) -> dict[str, Any]:
        """
        Analyzes codebase structure to identify testing priorities.

        Returns:
            Dict with module metadata (imports, complexity, etc.)
        """
        module_info = {}
        src_dir = self.repo_path / "src"
        for py_file in src_dir.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
            try:
                code = py_file.read_text()
                tree = ast.parse(code)
                imports = sum(
                    1
                    for node in ast.walk(tree)
                    if isinstance(node, (ast.Import, ast.ImportFrom))
                )
                classes = sum(
                    1 for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
                )
                functions = sum(
                    1 for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                )
                loc = len(
                    [
                        line
                        for line in code.splitlines()
                        if line.strip() and (not line.strip().startswith("#"))
                    ]
                )
                rel_path = str(py_file.relative_to(self.repo_path))
                module_info[rel_path] = {
                    "imports": imports,
                    "classes": classes,
                    "functions": functions,
                    "loc": loc,
                    "complexity_score": imports + classes + functions,
                }
            except Exception as e:
                logger.debug("Could not analyze {py_file}: %s", e)
        return module_info

    # ID: 09b41c82-55e9-494b-8387-bd92eeff3509
    def measure_coverage(self) -> dict[str, Any] | None:
        """
        Runs pytest with coverage and returns parsed results.

        Returns:
            Dict with coverage metrics or None if measurement fails
        """
        try:
            result = subprocess.run(
                [
                    "poetry",
                    "run",
                    "pytest",
                    "--cov=src",
                    "--cov-report=json",
                    "--cov-report=term",
                    "-q",
                ],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=300,
            )
            coverage_json = self.repo_path / "coverage.json"
            if coverage_json.exists():
                data = json.loads(coverage_json.read_text())
                totals = data.get("totals", {})
                return {
                    "overall_percent": totals.get("percent_covered", 0),
                    "lines_covered": totals.get("covered_lines", 0),
                    "lines_total": totals.get("num_statements", 0),
                    "files": data.get("files", {}),
                    "timestamp": data.get("meta", {}).get("timestamp"),
                }
            return self._parse_term_output(result.stdout)
        except subprocess.TimeoutExpired:
            logger.error("Coverage measurement timed out after 5 minutes")
            return None
        except Exception as e:
            logger.error("Failed to measure coverage: %s", e, exc_info=True)
            return None

    def _parse_term_output(self, output: str) -> dict[str, Any] | None:
        """
        Fallback parser for terminal coverage output.

        Args:
            output: Terminal output from pytest --cov

        Returns:
            Dict with coverage metrics or None
        """
        try:
            for line in output.splitlines():
                if line.startswith("TOTAL"):
                    parts = line.split()
                    if len(parts) >= 4:
                        percent_str = parts[-1].rstrip("%")
                        return {
                            "overall_percent": float(percent_str),
                            "lines_total": int(parts[1]),
                            "lines_covered": int(parts[1]) - int(parts[2]),
                        }
        except Exception as e:
            logger.debug("Failed to parse coverage output: %s", e)
        return None
