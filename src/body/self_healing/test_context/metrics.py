# src/features/self_healing/test_context/metrics.py

"""Refactored logic for src/features/self_healing/test_context/metrics.py."""

from __future__ import annotations

import ast
import json
import subprocess
from pathlib import Path


# ID: d5f0e7e2-e4aa-442c-8128-4bc8f6a95984
def get_coverage_data(repo_root: Path, module_path: str) -> dict:
    try:
        subprocess.run(
            ["pytest", f"--cov={repo_root}/src", "--cov-report=json", "-q"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
        cov_file = repo_root / "coverage.json"
        if cov_file.exists():
            data = json.loads(cov_file.read_text())
            file_key = str(repo_root / module_path)
            if file_key in data.get("files", {}):
                f_data = data["files"][file_key]
                uncovered = f_data.get("missing_lines", [])
                total = f_data.get("summary", {}).get("num_statements", 1)
                covered = f_data.get("summary", {}).get("covered_lines", 0)
                return {
                    "coverage": covered / total * 100,
                    "uncovered_lines": uncovered,
                    "uncovered_functions": map_lines_to_funcs(
                        repo_root / module_path, uncovered
                    ),
                }
    except Exception:
        pass
    return {"coverage": 0.0, "uncovered_lines": [], "uncovered_functions": []}


# ID: fa5f4fe3-e9c2-4946-b3f2-6fd85cf141ab
def map_lines_to_funcs(file_path: Path, lines: list[int]) -> list[str]:
    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
        return list(
            {
                n.name
                for n in ast.walk(tree)
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                and any(n.lineno <= ln <= (n.end_lineno or n.lineno) for ln in lines)
            }
        )
    except Exception:
        return []
