# src/mind/enforcement/audit.py

"""
Provides functionality for the audit module.

Refactored to be stateless and pure async (logic layer).
Now HEADLESS: Returns data, does not logger.info(LOG-001 compliance).

CONSTITUTIONAL FIX:
- Integrated with shared.infrastructure.validation.test_runner for Traceable Evidence.
- Promoted test_system to async-native.
"""

from __future__ import annotations

from shared.logger import getLogger


logger = getLogger(__name__)

from mind.governance.auditor import ConstitutionalAuditor
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.context import CoreContext
from shared.models import AuditFinding
from shared.utils.subprocess_utils import run_poetry_command


# ID: 7de7e5c2-0fbf-4028-8111-e3722b7d0ad9
async def run_audit_workflow(context: CoreContext) -> tuple[bool, list[AuditFinding]]:
    """
    The core async logic for running the audit.

    Returns:
        tuple(passed: bool, findings: list[AuditFinding])
    """
    # Inject Qdrant service from CoreContext into AuditorContext
    auditor_context = context.auditor_context
    if (
        auditor_context is not None
        and context.qdrant_service
        and not hasattr(auditor_context, "qdrant_service")
    ):
        auditor_context.qdrant_service = context.qdrant_service

    auditor = ConstitutionalAuditor(auditor_context)
    results = await auditor.run_full_audit_async()
    return results["passed"], results["findings"]


# ID: 09884f64-313e-4f9d-84d0-de9e2d16a8d3
def lint() -> None:
    """Checks code formatting and quality using Black and Ruff."""
    run_poetry_command(
        "🔎 Checking code format with Black...", ["black", "--check", "src", "tests"]
    )
    run_poetry_command(
        "🔎 Checking code quality with Ruff...", ["ruff", "check", "src", "tests"]
    )


@atomic_action(
    action_id="test.system",
    intent="Atomic action for test_system",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: 5963ab12-7398-4506-a257-0836ec585a88
async def test_system(core_context: CoreContext, **kwargs) -> ActionResult:
    """
    Run the project test suite via the canonical async test runner.

    This bridge ensures that test results are:
    1. Recorded in core.action_results (Database SSOT)
    2. Available as structured JSON evidence in var/reports/
    3. Interpretable by CORE agents and governance engines.

    Dispatches through ActionExecutor so the inner ``test.execute`` action
    runs with ``_executor_token == "test.execute"`` (ADR-079 identity
    propagation) rather than the enclosing ``test.system`` token.
    """
    if core_context.action_executor is None:
        return ActionResult(
            action_id="test.system",
            ok=False,
            data={"error": "action_executor not initialized"},
            impact=ActionImpact.WRITE_CODE,
        )
    return await core_context.action_executor.execute("test.execute")
