# src/mind/enforcement/audit.py

"""
Provides functionality for the audit module.

Refactored to be stateless and pure async (logic layer).
Now HEADLESS: Returns data, does not logger.info(LOG-001 compliance).
"""

from __future__ import annotations

from shared.logger import getLogger


logger = getLogger(__name__)

from mind.governance.auditor import ConstitutionalAuditor
from shared.context import CoreContext
from shared.models import AuditFinding, AuditSeverity
from shared.utils.subprocess_utils import run_poetry_command


# ID: 7de7e5c2-0fbf-4028-8111-e3722b7d0ad9
async def run_audit_workflow(context: CoreContext) -> tuple[bool, list[AuditFinding]]:
    """
    The core async logic for running the audit.

    Returns:
        tuple(passed: bool, findings: list[AuditFinding])
    """
    auditor = ConstitutionalAuditor(context.auditor_context)

    # The auditor handles its own activity logging and progress reporting
    # via AuditRunReporter (which is in Mind layer, thus allowed to print).
    all_findings_dicts = await auditor.run_full_audit_async()

    # Convert dicts back to models for the command layer
    severity_map = {str(s): s for s in AuditSeverity}
    all_findings = []
    for f_dict in all_findings_dicts:
        # Ensure we have a valid severity enum
        severity_val = f_dict.get("severity", "info")
        if isinstance(severity_val, str):
            f_dict["severity"] = severity_map.get(severity_val, AuditSeverity.INFO)
        all_findings.append(AuditFinding(**f_dict))

    # Determine pass/fail based on blocking errors
    blocking_errors = [f for f in all_findings if f.severity.is_blocking]
    passed = not bool(blocking_errors)

    return passed, all_findings


# ID: 09884f64-313e-4f9d-84d0-de9e2d16a8d3
def lint() -> None:
    """Checks code formatting and quality using Black and Ruff."""
    run_poetry_command(
        "🔎 Checking code format with Black...", ["black", "--check", "src", "tests"]
    )
    run_poetry_command(
        "🔎 Checking code quality with Ruff...", ["ruff", "check", "src", "tests"]
    )


# ID: 0a52d8ef-18a6-40c6-9ffe-95b9f9c295e4
def test_system() -> None:
    """Run the pytest suite."""
    run_poetry_command("🧪 Running tests with pytest...", ["pytest"])
