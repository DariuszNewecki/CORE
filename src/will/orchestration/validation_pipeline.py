# src/will/orchestration/validation_pipeline.py

"""
A context-aware validation pipeline that applies different validation steps based on file type.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from services.storage.file_classifier import get_file_classification
from services.validation.python_validator import validate_python_code_async
from services.validation.yaml_validator import validate_yaml_code
from shared.logger import getLogger

if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext
logger = getLogger(__name__)


# ID: 49007f0d-d279-449b-9a47-da13fb6a0a5e
async def validate_code_async(
    file_path: str,
    code: str,
    quiet: bool = False,
    auditor_context: AuditorContext | None = None,
) -> dict[str, Any]:
    """Validate a file's code by routing it to the appropriate validation pipeline."""
    classification = get_file_classification(file_path)
    if not quiet:
        logger.debug("Validation: Classifying '{file_path}' as '%s'.", classification)
    final_code = code
    violations = []
    if classification == "python":
        if not auditor_context:
            raise ValueError("AuditorContext is required for validating Python code.")
        final_code, violations = await validate_python_code_async(
            file_path, code, auditor_context
        )
    elif classification == "yaml":
        final_code, violations = validate_yaml_code(code)
    is_dirty = any(v.get("severity") == "error" for v in violations)
    status = "dirty" if is_dirty else "clean"
    return {"status": status, "violations": violations, "code": final_code}
