# src/core/validation_pipeline.py
"""
A context-aware validation pipeline that applies different validation steps
based on the type of file being processed. This is the single source of truth
for all code and configuration validation.
"""
import ast
import yaml
from pathlib import Path
from typing import List, Dict, Any

from core.black_formatter import format_code_with_black
from core.ruff_linter import fix_and_lint_code_with_ruff
from core.syntax_checker import check_syntax

FORBIDDEN_CALLS = {
    "eval", "exec", "compile", "os.system", "subprocess.run",
    "subprocess.Popen", "os.remove", "os.rmdir", "shutil.rmtree",
}
FORBIDDEN_IMPORTS = {"socket", "shutil", "pickle", "shelve"}

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

def _find_dangerous_patterns(tree: ast.AST) -> List[str]:
    """Scans the AST for calls to forbidden functions and imports."""
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            full_call_name = ""
            if isinstance(node.func, ast.Name): full_call_name = node.func.id
            elif isinstance(node.func, ast.Attribute): full_call_name = _get_full_attribute_name(node.func)
            if full_call_name in FORBIDDEN_CALLS:
                violations.append(f"Use of forbidden call on line {node.lineno}: '{full_call_name}'")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in FORBIDDEN_IMPORTS:
                    violations.append(f"Import of forbidden module on line {node.lineno}: '{alias.name}'")
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in FORBIDDEN_IMPORTS:
                violations.append(f"Import from forbidden module on line {node.lineno}: '{node.module}'")
    return violations

# CAPABILITY: semantic_validation
def _check_semantics(code: str) -> List[str]:
    """Runs all semantic checks on a string of Python code."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return [f"SyntaxError during semantic check: {e}"]
    return _find_dangerous_patterns(tree)

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
    semantic_errors = _check_semantics(fixed_code)
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
def validate_code(file_path: str, code: str) -> Dict[str, Any]:
    """
    The main entry point for validation. It determines the file type
    and routes it to the appropriate, specific validation function.
    """
    classification = _get_file_classification(file_path)
    print(f"  -> Validation: Classifying '{file_path}' as '{classification}'. Routing to validator.")
    if classification == "python":
        return _validate_python_code(file_path, code)
    if classification == "yaml":
        return _validate_yaml(code)
    return {"status": "clean", "errors": [], "code": code}