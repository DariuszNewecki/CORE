# src/core/validation_pipeline.py
"""
A context-aware validation pipeline that applies different validation steps
based on the type of file being processed. This is the single source of truth
for all code and configuration validation.
"""
import ast
import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional

from core.black_formatter import format_code_with_black
from core.ruff_linter import fix_and_lint_code_with_ruff
from core.syntax_checker import check_syntax
from shared.config_loader import load_config
from shared.path_utils import get_repo_root
from shared.logger import getLogger

log = getLogger(__name__)

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

def _find_dangerous_patterns(tree: ast.AST, file_path: str) -> List[str]:
    """Scans the AST for calls to functions and imports forbidden by safety policies."""
    violations = []
    rules = _load_safety_policies()
    
    # Dynamically build the set of forbidden patterns for this specific file
    forbidden_calls = set()
    forbidden_imports = set()

    for rule in rules:
        # Check if the file is excluded from this rule
        is_excluded = any(Path(file_path).match(p) for p in rule.get("scope", {}).get("exclude", []))
        if is_excluded:
            continue

        # Add patterns from the rule if not excluded
        if rule.get("id") == "no_dangerous_execution":
            patterns = {p.replace('(', '') for p in rule.get("detection", {}).get("patterns", [])}
            forbidden_calls.update(patterns)
        elif rule.get("id") == "no_unsafe_imports":
            patterns = {imp.split(' ')[-1] for imp in rule.get("detection", {}).get("forbidden", [])}
            forbidden_imports.update(patterns)
            
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            full_call_name = ""
            if isinstance(node.func, ast.Name): full_call_name = node.func.id
            elif isinstance(node.func, ast.Attribute): full_call_name = _get_full_attribute_name(node.func)
            if full_call_name in forbidden_calls:
                violations.append(f"Use of forbidden call on line {node.lineno}: '{full_call_name}'")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in forbidden_imports:
                    violations.append(f"Import of forbidden module on line {node.lineno}: '{alias.name}'")
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in forbidden_imports:
                violations.append(f"Import from forbidden module on line {node.lineno}: '{node.module}'")
    return violations

# CAPABILITY: semantic_validation
def _check_semantics(code: str, file_path: str) -> List[str]:
    """Runs all policy-aware semantic checks on a string of Python code."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return [f"SyntaxError during semantic check: {e}"]
    return _find_dangerous_patterns(tree, file_path)

def _validate_python_code(path_hint: str, code: str) -> Dict[str, Any]:
    """Runs the full validation suite for Python code: format, lint, syntax, and semantics."""
    errors: List[str] = []
    formatted_code, fmt_err = format_code_with_black(code)
    if fmt_err:
        errors.append(f"Black Formatter Failed: {fmt_err}")
        return {"status": "dirty", "errors": errors, "code": code}
    
    is_clean, lint_msg, fixed_code = fix_and_lint_code_with_ruff(formatted_code)
    if not is_clean:
        errors.append(f"Ruff Linter Found Unfixable Issues:\n{lint_msg}")
    
    syntax_valid, syntax_msg = check_syntax(path_hint, fixed_code)
    if not syntax_valid:
        errors.append(f"Syntax Error: {syntax_msg}")
        return {"status": "dirty", "errors": errors, "code": fixed_code}
    
    semantic_errors = _check_semantics(fixed_code, path_hint)
    if semantic_errors:
        errors.extend(semantic_errors)
    
    status = "clean" if not errors else "dirty"
    return {"status": status, "errors": errors, "code": fixed_code}

def _validate_yaml(code: str) -> Dict[str, Any]:
    """Runs validation steps specific to YAML files."""
    errors = []
    try:
        yaml.safe_load(code)
    except yaml.YAMLError as e:
        errors.append(f"Invalid YAML format: {e}")
    status = "clean" if not errors else "dirty"
    return {"status": status, "errors": errors, "code": code}

def _get_file_classification(file_path: str) -> str:
    """Determines the file type based on its extension."""
    suffix = Path(file_path).suffix.lower()
    if suffix == ".py": return "python"
    if suffix in [".yaml", ".yml"]: return "yaml"
    if suffix in [".md", ".txt", ".json"]: return "text"
    return "unknown"

# CAPABILITY: code_quality_analysis
def validate_code(file_path: str, code: str, quiet: bool = False) -> Dict[str, Any]:
    """
    The main entry point for validation. It determines the file type
    and routes it to the appropriate, specific validation function.
    """
    classification = _get_file_classification(file_path)
    if not quiet:
        log.debug(f"Validation: Classifying '{file_path}' as '{classification}'.")
    
    if classification == "python":
        return _validate_python_code(file_path, code)
    if classification == "yaml":
        return _validate_yaml(code)
    return {"status": "clean", "errors": [], "code": code}