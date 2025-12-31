# src/features/self_healing/complexity_service.py
# ID: 453e06ba-139f-427c-bbe3-ff590640b766

"""
Administrative tool for identifying and refactoring code complexity outliers.
Refactored to use the canonical ActionExecutor Gateway for all mutations.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from body.atomic.executor import ActionExecutor
from mind.governance.audit_context import AuditorContext
from shared.config import settings
from shared.logger import getLogger
from shared.utils.parsing import extract_json_from_response, parse_write_blocks
from will.orchestration.validation_pipeline import validate_code_async


if TYPE_CHECKING:
    from shared.context import CoreContext
    from will.orchestration.cognitive_service import CognitiveService

logger = getLogger(__name__)
REPO_ROOT = settings.REPO_PATH


def _get_capabilities_from_code(code: str) -> list[str]:
    """A simple parser to extract # CAPABILITY tags from a string of code."""
    return re.findall("#\\s*CAPABILITY:\\s*(\\S+)", code)


async def _propose_constitutional_amendment(
    executor: ActionExecutor, proposal_plan: dict[str, Any], write: bool
) -> bool:
    """Creates a formal proposal file via the governed Action Gateway."""
    target_file_name = Path(proposal_plan["target_path"]).stem

    # We use a deterministic but unique ID for the proposal file
    import uuid

    proposal_id = str(uuid.uuid4())[:8]
    proposal_filename = f"cr-refactor-{target_file_name}-{proposal_id}.yaml"

    # Resolve relative path for the proposals directory
    proposals_dir_rel = str(settings.paths.proposals_dir.relative_to(REPO_ROOT))
    proposal_rel_path = f"{proposals_dir_rel}/{proposal_filename}"

    proposal_content = {
        "target_path": proposal_plan["target_path"],
        "action": "replace_file",
        "justification": proposal_plan["justification"],
        "content": proposal_plan["content"],
    }

    yaml_str = yaml.dump(proposal_content, indent=2, sort_keys=False)

    # CONSTITUTIONAL GATEWAY: Create the proposal file
    result = await executor.execute(
        action_id="file.create", write=write, file_path=proposal_rel_path, code=yaml_str
    )

    if result.ok:
        logger.info("Constitutional amendment proposed at: %s", proposal_rel_path)
        return True

    logger.error("Failed to create proposal: %s", result.data.get("error"))
    return False


async def _run_capability_reconciliation(
    cognitive_service: CognitiveService,
    original_code: str,
    original_capabilities: list[str],
    refactoring_plan: dict[str, str],
) -> dict[str, Any]:
    """
    Asks an AI Constitutionalist to analyze the refactoring and reconcile tags.
    """
    logger.info("Asking AI Constitutionalist to reconcile capabilities...")
    refactored_code_json = json.dumps(refactoring_plan, indent=2)

    prompt = (
        "You are an expert CORE Constitutionalist. You understand that a good refactoring not only improves code but also clarifies purpose.\n"
        f"The original file provided these capabilities: {original_capabilities}\n"
        f"A refactoring has occurred, resulting in these new files:\n{refactored_code_json}\n"
        "Your task is to produce a JSON object with: 'code_modifications' (file paths mapped to code with updated tags) "
        "and 'constitutional_amendment_proposal' (if new capabilities should be declared).\n"
        "Return ONLY a valid JSON object."
    )

    constitutionalist = await cognitive_service.aget_client_for_role("Planner")
    response = await constitutionalist.make_request_async(
        prompt, user_id="constitutionalist_agent"
    )

    try:
        reconciliation_result = extract_json_from_response(response)
        if not reconciliation_result:
            raise ValueError("No valid JSON object found.")
        return reconciliation_result
    except Exception as e:
        logger.error("Failed to parse reconciliation plan: %s", e)
        return {
            "code_modifications": refactoring_plan,
            "constitutional_amendment_proposal": None,
        }


async def _async_complexity_outliers(
    context: CoreContext, file_path: Path | None, dry_run: bool
):
    """
    Async core logic for identifying and refactoring complexity outliers.
    Mutations are routed through the governed ActionExecutor.
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

        # 3. Validation & Reconciliation
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


# ID: 453e06ba-139f-427c-bbe3-ff590640b766
async def complexity_outliers(
    context: CoreContext,
    file_path: Path | None,
    dry_run: bool = True,
):
    """Identifies and refactors complexity outliers via governed actions."""
    await _async_complexity_outliers(context, file_path, dry_run)
