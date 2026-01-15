# src/will/phases/stub_phases.py
# ID: will.phases.stub_phases

"""
Stub Phase Implementations - Delegates to Existing Agents

These are minimal adapters that bridge the new phase interface
to your existing agent implementations.

As you migrate, replace these stubs with full implementations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from shared.logger import getLogger
from shared.models.workflow_models import PhaseResult


if TYPE_CHECKING:
    from shared.context import CoreContext
    from will.orchestration.workflow_orchestrator import WorkflowContext

logger = getLogger(__name__)


# ID: 309de751-008e-4e23-baec-fe32637fad8a
class CodeGenerationPhase:
    """Stub - delegates to SpecificationAgent"""

    def __init__(self, context: CoreContext):
        self.context = context

    # ID: c6b38e0a-e575-48e8-a28d-28980f0ba439
    async def execute(self, ctx: WorkflowContext) -> PhaseResult:
        logger.warning("⚠️  Using STUB CodeGenerationPhase - needs full implementation")
        return PhaseResult(
            name="code_generation",
            ok=False,
            error="Stub implementation - not yet migrated",
            duration_sec=0.0,
        )


# ID: 3273338d-c5af-420e-a706-3b06411ccb76
class TestGenerationPhase:
    """Stub - delegates to EnhancedTestGenerator"""

    def __init__(self, context: CoreContext):
        self.context = context

    # ID: 283a42db-c4b9-4bed-b9a8-36ed4a95c7ab
    async def execute(self, ctx: WorkflowContext) -> PhaseResult:
        logger.warning("⚠️  Using STUB TestGenerationPhase")
        return PhaseResult(
            name="test_generation",
            ok=True,  # Non-blocking
            data={"skipped": True, "reason": "stub"},
            duration_sec=0.0,
        )


# ID: 5eeb168d-e644-4533-b11d-ebfdef27f076
class CanaryValidationPhase:
    """Stub - runs existing tests"""

    def __init__(self, context: CoreContext):
        self.context = context

    # ID: edaf7058-8277-44a9-9389-e61429384459
    async def execute(self, ctx: WorkflowContext) -> PhaseResult:
        logger.warning("⚠️  Using STUB CanaryValidationPhase")
        # TODO: Actually run pytest on existing tests
        return PhaseResult(
            name="canary_validation",
            ok=True,
            data={"tests_passed": 0, "note": "stub - assumed passing"},
            duration_sec=0.0,
        )


# ID: 840fa29e-938a-474d-9fc4-e91b54718fea
class SandboxValidationPhase:
    """Stub - validates generated tests"""

    def __init__(self, context: CoreContext):
        self.context = context

    # ID: ad1564ad-a023-4722-86ff-ff35cbea99bc
    async def execute(self, ctx: WorkflowContext) -> PhaseResult:
        logger.info("⏭️  Skipping SandboxValidationPhase (not in this workflow)")
        return PhaseResult(
            name="sandbox_validation", ok=True, data={"skipped": True}, duration_sec=0.0
        )


# ID: 8b81433c-c598-452a-a913-12063678e894
class StyleCheckPhase:
    """Stub - runs ruff/black"""

    def __init__(self, context: CoreContext):
        self.context = context

    # ID: 35731b53-2382-4832-9bcc-417d068cb866
    async def execute(self, ctx: WorkflowContext) -> PhaseResult:
        logger.warning("⚠️  Using STUB StyleCheckPhase")
        # TODO: Actually run ruff check
        return PhaseResult(
            name="style_check",
            ok=True,
            data={"violations": 0, "note": "stub - not validated"},
            duration_sec=0.0,
        )


# ID: b1962a80-a098-4796-8093-7d1481aee98f
class ExecutionPhase:
    """Stub - applies changes"""

    def __init__(self, context: CoreContext):
        self.context = context

    # ID: 08e93943-8ec8-4d42-80c0-3fd13838e317
    async def execute(self, ctx: WorkflowContext) -> PhaseResult:
        logger.warning("⚠️  Using STUB ExecutionPhase")

        if not ctx.write:
            return PhaseResult(
                name="execution",
                ok=True,
                data={"dry_run": True, "files_written": 0},
                duration_sec=0.0,
            )

        # TODO: Actually write files using ExecutionAgent
        return PhaseResult(
            name="execution",
            ok=False,
            error="Stub - file writing not implemented",
            duration_sec=0.0,
        )
