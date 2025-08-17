# src/core/validation_pipeline.py
"""
A context-aware validation pipeline that applies different validation steps
based on the type of file being processed. This is the single source of truth
for all code and configuration validation.
"""
import ast
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import black
import yaml

from core.black_formatter import format_code_with_black
from core.ruff_linter import fix_and_lint_code_with_ruff
from core.syntax_checker import check_syntax
from shared.config_loader import load_config
from shared.logger import getLogger
from shared.path_utils import get_repo_root

log = getLogger(__name__)
Violation = Dict[str, Any]

# --- Policy-Aware Validation ---

_safety_policies_cache: Optional[List[Dict]] = None


def _load_safety_policies() -> List[Dict]:
    """Loads and caches the safety policies from the .intent directory."""
    global _safety_policies_cache
    if _safety_policies_cache is None:
        repo_root = get_repo_root()
        policies_path = repo_root / ".intent" / "policies" / "safety_policies.yaml"
        policy_data = load_config(policies_path, "yaml")
        _safety_policies_cache = policy_data.get("rules", [])
    return _safety_policies_cache


def _get_full_attribute_name(node: ast.Attribute) -> str:
    """Recursively builds the full name of an attribute call (e.g., 'os.path.join')."""
    parts = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.insert(0, current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.insert(0, current.id)
    return ".".join(parts)


def _find_dangerous_patterns(tree: ast.AST, file_path: str) -> List[Violation]:
    """Scans the AST for calls and imports forbidden by safety policies."""
    violations: List[Violation] = []
    rules = _load_safety_policies()

    forbidden_calls = set()
    forbidden_imports = set()

    for rule in rules:
        # --- THIS IS THE FIX ---
        # The original code did not check if the items in the 'exclude' list were strings.
        # We now ensure we only try to match string patterns, gracefully ignoring other types.
        exclude_patterns = [
            p for p in rule.get("scope", {}).get("exclude", []) if isinstance(p, str)
        ]
        is_excluded = any(Path(file_path).match(p) for p in exclude_patterns)
        # --- END OF FIX ---

        if is_excluded:
            continue

        if rule.get("id") == "no_dangerous_execution":
            patterns = {
                p.replace("(", "")
                for p in rule.get("detection", {}).get("patterns", [])
            }
            forbidden_calls.update(patterns)
        elif rule.get("id") == "no_unsafe_imports":
            patterns = {
                imp.split(" ")[-1]
                for imp in rule.get("detection", {}).get("forbidden", [])
            }
            forbidden_imports.update(patterns)

    for node in ast.walk(tree):
        # Check for dangerous function calls
        if isinstance(node, ast.Call):
            full_call_name = ""
            if isinstance(node.func, ast.Name):
                full_call_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                full_call_name = _get_full_attribute_name(node.func)

            if full_call_name in forbidden_calls:
                violations.append(
                    {
                        "rule": "safety.dangerous_call",
                        "message": f"Use of forbidden call: '{full_call_name}'",
                        "line": node.lineno,
                        "severity": "error",
                    }
                )
        # Check for forbidden imports
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in forbidden_imports:
                    violations.append(
                        {
                            "rule": "safety.forbidden_import",
                            "message": f"Import of forbidden module: '{alias.name}'",
                            "line": node.lineno,
                            "severity": "error",
                        }
                    )
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in forbidden_imports:
                violations.append(
                    {
                        "rule": "safety.forbidden_import",
                        "message": f"Import from forbidden module: '{node.module}'",
                        "line": node.lineno,
                        "severity": "error",
                    }
                )
    return violations


def _check_for_todo_comments(code: str) -> List[Violation]:
    """Scans source code for TODO/FIXME comments and returns them as violations."""
    violations: List[Violation] = []
    for i, line in enumerate(code.splitlines(), 1):
        if "#" in line:
            comment = line.split("#", 1)[1]
            if "TODO" in comment or "FIXME" in comment:
                violations.append(
                    {
                        "rule": "clarity.no_todo_comments",
                        "message": f"Unresolved '{comment.strip()}' on line {i}",
                        "line": i,
                        "severity": "warning",
                    }
                )
    return violations


# CAPABILITY: semantic_validation
def _check_semantics(code: str, file_path: str) -> List[Violation]:
    """Runs all policy-aware semantic checks on a string of Python code."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        # Syntax errors are caught by check_syntax, so we can ignore them here.
        return []
    return _find_dangerous_patterns(tree, file_path)


def _validate_python_code(path_hint: str, code: str) -> Tuple[str, List[Violation]]:
    """
    Internal pipeline for Python code validation.
    Returns the final code and a list of all found violations.
    """
    all_violations: List[Violation] = []

    # 1. Format with Black. This can fail on major syntax errors.
    try:
        formatted_code = format_code_with_black(code)
    except (black.InvalidInput, Exception) as e:
        # If Black fails, the code is fundamentally broken.
        all_violations.append(
            {
                "rule": "tooling.black_failure",
                "message": str(e),
                "line": 0,
                "severity": "error",
            }
        )
        # Return the original code since formatting failed.
        return code, all_violations

    # 2. Lint with Ruff (which also fixes).
    fixed_code, ruff_violations = fix_and_lint_code_with_ruff(formatted_code, path_hint)
    all_violations.extend(ruff_violations)

    # 3. Check syntax on the post-Ruff code.
    syntax_violations = check_syntax(path_hint, fixed_code)
    all_violations.extend(syntax_violations)
    # If there's a syntax error, no further checks are reliable.
    if any(v["severity"] == "error" for v in syntax_violations):
        return fixed_code, all_violations

    # 4. Perform semantic and clarity checks on the valid code.
    all_violations.extend(_check_semantics(fixed_code, path_hint))
    all_violations.extend(_check_for_todo_comments(fixed_code))

    return fixed_code, all_violations


def _validate_yaml(code: str) -> Tuple[str, List[Violation]]:
    """Internal pipeline for YAML validation."""
    violations = []
    try:
        yaml.safe_load(code)
    except yaml.YAMLError as e:
        violations.append(
            {
                "rule": "syntax.yaml",
                "message": f"Invalid YAML format: {e}",
                "line": e.problem_mark.line + 1 if e.problem_mark else 0,
                "severity": "error",
            }
        )
    return code, violations


def _get_file_classification(file_path: str) -> str:
    """Determines the file type based on its extension."""
    suffix = Path(file_path).suffix.lower()
    if suffix == ".py":
        return "python"
    if suffix in [".yaml", ".yml"]:
        return "yaml"
    if suffix in [".md", ".txt", ".json"]:
        return "text"
    return "unknown"


# CAPABILITY: code_quality_analysis
def validate_code(file_path: str, code: str, quiet: bool = False) -> Dict[str, Any]:
    """Validate a file's code by routing it to the appropriate validation pipeline based on its file type, returning a standardized dictionary with status, violations, and processed code."""
    """
    The main entry point for validation. It determines the file type
    and routes it to the appropriate validation pipeline, returning a
    standardized dictionary.
    """
    classification = _get_file_classification(file_path)
    if not quiet:
        log.debug(f"Validation: Classifying '{file_path}' as '{classification}'.")

    final_code = code
    violations: List[Violation] = []

    if classification == "python":
        final_code, violations = _validate_python_code(file_path, code)
    elif classification == "yaml":
        final_code, violations = _validate_yaml(code)

    # Determine final status. "dirty" if there are any 'error' severity violations.
    is_dirty = any(v.get("severity") == "error" for v in violations)
    status = "dirty" if is_dirty else "clean"

    return {"status": status, "violations": violations, "code": final_code}
