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
from typing import Any

from shared.config import settings
from shared.logger import getLogger

log = getLogger(__name__)


# ID: TBD
# ID: 0a408641-8cb8-464a-9ca1-ca0b3ba19315
class CoverageAnalyzer:
    """
    Analyzes test coverage and module structure for prioritization.
    """

    def __init__(self):
        self.repo_path = settings.REPO_PATH

    # ID: 56cb209a-33b3-4016-8c26-e03d6be75bbe
    def get_module_coverage(self) -> dict[str, float]:
        """
        Gets current coverage percentage for each module.

        Returns:
            Dict mapping file paths to coverage percentages
        """
        try:
            # Run coverage
            subprocess.run(
                ["poetry", "run", "pytest", "--cov=src", "--cov-report=json", "-q"],
                cwd=self.repo_path,
                capture_output=True,
                timeout=120,
            )

            # Read JSON report
            coverage_json = self.repo_path / "coverage.json"
            if coverage_json.exists():
                data = json.loads(coverage_json.read_text())

                # Extract per-file coverage
                module_coverage = {}
                for file_path, file_data in data.get("files", {}).items():
                    summary = file_data.get("summary", {})
                    percent = summary.get("percent_covered", 0)
                    module_coverage[file_path] = round(percent, 2)

                return module_coverage
        except Exception as e:
            log.debug(f"Could not get module coverage: {e}")

        return {}

    # ID: 7cea3c1c-466f-4290-b9c5-04a3e678a0e4
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

                # Count imports (proxy for dependencies)
                imports = sum(
                    1
                    for node in ast.walk(tree)
                    if isinstance(node, (ast.Import, ast.ImportFrom))
                )

                # Count classes and functions (proxy for complexity)
                classes = sum(
                    1 for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
                )
                functions = sum(
                    1 for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                )

                # Calculate lines of code
                loc = len(
                    [
                        line
                        for line in code.splitlines()
                        if line.strip() and not line.strip().startswith("#")
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
                log.debug(f"Could not analyze {py_file}: {e}")

        return module_info

    # ID: 478b8189-00a2-456b-a469-967b5a7cf750
    def measure_coverage(self) -> dict[str, Any] | None:
        """
        Runs pytest with coverage and returns parsed results.

        Returns:
            Dict with coverage metrics or None if measurement fails
        """
        try:
            # Run pytest with JSON report for machine parsing
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
                timeout=300,  # 5 minute timeout
            )

            # Read the JSON report
            coverage_json = self.repo_path / "coverage.json"
            if coverage_json.exists():
                data = json.loads(coverage_json.read_text())

                # Extract key metrics
                totals = data.get("totals", {})
                return {
                    "overall_percent": totals.get("percent_covered", 0),
                    "lines_covered": totals.get("covered_lines", 0),
                    "lines_total": totals.get("num_statements", 0),
                    "files": data.get("files", {}),
                    "timestamp": data.get("meta", {}).get("timestamp"),
                }

            # Fallback: parse terminal output
            return self._parse_term_output(result.stdout)

        except subprocess.TimeoutExpired:
            log.error("Coverage measurement timed out after 5 minutes")
            return None
        except Exception as e:
            log.error(f"Failed to measure coverage: {e}", exc_info=True)
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
            # Look for TOTAL line: "TOTAL    1234    567    54%"
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
            log.debug(f"Failed to parse coverage output: {e}")

        return None
