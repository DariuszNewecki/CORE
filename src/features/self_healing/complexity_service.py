# src/features/self_healing/complexity_service.py
# ID: 453e06ba-139f-427c-bbe3-ff590640b766

"""
Complexity Outlier Refactoring Service - Main Orchestrator

CONSTITUTIONAL ALIGNMENT:
- Single Responsibility: Orchestrate complexity refactoring workflow
- Delegates to specialized services
- Uses ActionExecutor for all mutations

Extracted responsibilities:
- Capability parsing → CapabilityParser
- Proposal writing → RefactoringProposalWriter
- Capability reconciliation → CapabilityReconciliationService

Architecture:
Administrative tool for identifying and refactoring code complexity outliers.
All mutations routed through canonical ActionExecutor Gateway.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from body.atomic.executor import ActionExecutor
from mind.governance.audit_context import AuditorContext
from shared.config import settings
from shared.logger import getLogger
from shared.utils.parsing import parse_write_blocks
from will.orchestration.validation_pipeline import validate_code_async


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)
REPO_ROOT = settings.REPO_PATH


# ID: complexity_outliers_async
# ID: 8b9c0d1e-2f3a-4b5c-6d7e-8f9a0b1c2d3e
async def _async_complexity_outliers(
    context: CoreContext, file_path: Path | None, dry_run: bool
):
    """
    Core logic for identifying and refactoring complexity outliers.

    Orchestration workflow:
    1. Get AI architectural plan
    2. Validate generated code
    3. Execute governed file operations (delete + create)

    Args:
        context: CoreContext with cognitive service and configuration
        file_path: Target file to refactor
        dry_run: If True, simulate without writing
    """
    if not file_path:
        logger.error("Please provide a specific file path to refactor.")
        return

    rel_target = str(file_path.relative_to(REPO_ROOT))
    logger.info("Starting complexity refactor cycle for: %s", rel_target)

    # 1. Setup Governed Environment
    executor = ActionExecutor(context)
    cognitive_service = context.cognitive_service
    auditor_context = AuditorContext(REPO_ROOT)
    await auditor_context.load_knowledge_graph()

    try:
        # 2. Get AI Architectural Plan (Will)
        source_code = file_path.read_text(encoding="utf-8")
        prompt_path = settings.paths.prompt("refactor_outlier")
        prompt_template = prompt_path.read_text(encoding="utf-8").replace(
            "{source_code}", source_code
        )

        refactor_client = await cognitive_service.aget_client_for_role(
            "RefactoringArchitect"
        )
        response = await refactor_client.make_request_async(
            prompt_template, user_id="refactoring_agent"
        )

        refactoring_plan = parse_write_blocks(response)
        if not refactoring_plan:
            raise ValueError("No valid [[write:]] blocks found in AI response.")

        # 3. Validation Phase
        validated_code_plan = {}
        for path, code in refactoring_plan.items():
            val_result = await validate_code_async(
                path, str(code), auditor_context=auditor_context
            )
            if val_result["status"] == "dirty":
                raise RuntimeError(
                    f"AI generated invalid code for '{path}': {val_result['violations']}"
                )
            validated_code_plan[path] = val_result["code"]

        # 4. Governed Execution (Body)
        write_mode = not dry_run

        # Step A: Delete the original outlier (Atomic Delete)
        del_result = await executor.execute(
            action_id="file.delete", write=write_mode, file_path=rel_target
        )

        if not del_result.ok:
            logger.error(
                "❌ Refactor aborted: Could not delete original file: %s",
                del_result.data.get("error"),
            )
            return

        # Step B: Create the new, refactored files (Atomic Create)
        for path, code in validated_code_plan.items():
            create_result = await executor.execute(
                action_id="file.create", write=write_mode, file_path=path, code=code
            )

            if create_result.ok:
                status = "Created" if write_mode else "Proposed"
                logger.info("   -> [%s] %s", status, path)
            else:
                logger.error(
                    "   -> [FAILED] %s: %s", path, create_result.data.get("error")
                )

        logger.info(
            "Refactoring orchestration complete. Sync with 'core-admin dev sync' to update graph."
        )

    except Exception as e:
        logger.error("Refactoring failed for %s: %s", rel_target, e, exc_info=True)


# ID: complexity_outliers
# ID: 453e06ba-139f-427c-bbe3-ff590640b766
async def complexity_outliers(
    context: CoreContext,
    file_path: Path | None,
    dry_run: bool = True,
):
    """
    Identifies and refactors complexity outliers via governed actions.

    Public entry point for complexity refactoring workflow.

    Args:
        context: CoreContext with dependencies
        file_path: File to refactor
        dry_run: If True, simulate without writing
    """
    await _async_complexity_outliers(context, file_path, dry_run)
