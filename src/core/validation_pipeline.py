# src/core/validation_pipeline.py
"""
A context-aware validation pipeline that applies different validation steps based on file type, serving as the single source of truth for all code and configuration validation.

This module acts as the main entry point for validation, routing files to appropriate
validation pipelines based on their type and returning standardized results.
"""

from __future__ import annotations

from typing import Any, Dict

from shared.logger import getLogger

from .file_classifier import get_file_classification
from .python_validator import validate_python_code
from .yaml_validator import validate_yaml_code

log = getLogger(__name__)


# CAPABILITY: route_files_to_appropriate_validation_pipeline
def validate_code(file_path: str, code: str, quiet: bool = False) -> Dict[str, Any]:
    """Validate a file's code by routing it to the appropriate validation pipeline based on its file type.

    This is the main entry point for validation. It determines the file type
    and routes it to the appropriate validation pipeline, returning a
    standardized dictionary with status, violations, and processed code.

    Args:
        file_path: Path to the file being validated
        code: The source code to validate
        quiet: If True, suppress debug logging

    Returns:
        A dictionary containing validation status, violations list, and processed code
    """
    classification = get_file_classification(file_path)
    if not quiet:
        log.debug(f"Validation: Classifying '{file_path}' as '{classification}'.")

    final_code = code
    violations = []

    if classification == "python":
        final_code, violations = validate_python_code(file_path, code)
    elif classification == "yaml":
        final_code, violations = validate_yaml_code(code)

    # Determine final status. "dirty" if there are any 'error' severity violations.
    is_dirty = any(v.get("severity") == "error" for v in violations)
    status = "dirty" if is_dirty else "clean"

    return {"status": status, "violations": violations, "code": final_code}
