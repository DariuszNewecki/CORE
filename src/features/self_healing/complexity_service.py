# src/features/self_healing/complexity_service.py

"""
Administrative tool for identifying and refactoring code complexity outliers.
This version includes a "Semantic Capability Reconciliation" step to ensure
that refactoring not only improves the code but also proposes necessary
amendments to the system's constitution.
"""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from pathlib import Path
from typing import Any

import typer
import yaml
from rich.console import Console
from rich.panel import Panel

from mind.governance.audit_context import AuditorContext
from shared.config import settings
from shared.context import CoreContext
from shared.logger import getLogger
from shared.utils.parsing import extract_json_from_response, parse_write_blocks
from will.orchestration.cognitive_service import CognitiveService
from will.orchestration.validation_pipeline import validate_code_async

logger = getLogger(__name__)
console = Console()
REPO_ROOT = settings.REPO_PATH


def _get_capabilities_from_code(code: str) -> list[str]:
    """A simple parser to extract # CAPABILITY tags from a string of code."""
    return re.findall("#\\s*CAPABILITY:\\s*(\\S+)", code)


def _propose_constitutional_amendment(proposal_plan: dict[str, Any]):
    """Creates a formal proposal file for a constitutional amendment."""
    proposal_dir = REPO_ROOT / ".intent" / "proposals"
    proposal_dir.mkdir(exist_ok=True)
    target_file_name = Path(proposal_plan["target_path"]).stem
    proposal_id = str(uuid.uuid4())[:8]
    proposal_filename = f"cr-refactor-{target_file_name}-{proposal_id}.yaml"
    proposal_path = proposal_dir / proposal_filename
    proposal_content = {
        "target_path": proposal_plan["target_path"],
        "action": "replace_file",
        "justification": proposal_plan["justification"],
        "content": yaml.dump(
            proposal_plan["content"], indent=2, default_flow_style=False
        ),
    }
    proposal_path.write_text(
        yaml.dump(proposal_content, indent=2, sort_keys=False), encoding="utf-8"
    )
    logger.info(
        f"📄 Constitutional amendment proposed at: {proposal_path.relative_to(REPO_ROOT)}"
    )
    return True


async def _run_capability_reconciliation(
    cognitive_service: CognitiveService,
    original_code: str,
    original_capabilities: list[str],
    refactoring_plan: dict[str, str],
) -> dict[str, Any]:
    """
    Asks an AI Constitutionalist to analyze the refactoring, re-tag capabilities,
    and propose manifest changes.
    """
    logger.info("🏛️  Asking AI Constitutionalist to reconcile capabilities...")
    refactored_code_json = json.dumps(refactoring_plan, indent=2)
    prompt = f"""\nYou are an expert CORE Constitutionalist. You understand that a good refactoring not only improves code but also clarifies purpose.\nThe original file provided these capabilities: {original_capabilities}\nA refactoring has occurred, resulting in these new files:\n{refactored_code_json}\nYour task is to perform a semantic analysis and produce a JSON object with two keys: "code_modifications" and "constitutional_amendment_proposal".\n1.  **code_modifications**: This should be a JSON object where keys are file paths and values are the complete, final source code WITH the original capabilities correctly re-tagged onto the new functions that now hold that responsibility.\n2.  **constitutional_amendment_proposal**: If the refactoring has clarified purpose and new, more atomic capabilities should exist, define a manifest change proposal. If no change is needed, this key should be null. The proposal should have 'target_path', 'justification', and 'content' for the new manifest.\nYour entire output must be a single, valid JSON object.\n"""
    constitutionalist = await cognitive_service.aget_client_for_role("Planner")
    response = await constitutionalist.make_request_async(
        prompt, user_id="constitutionalist_agent"
    )
    try:
        reconciliation_result = extract_json_from_response(response)
        if not reconciliation_result:
            raise ValueError("No valid JSON object found in the AI's response.")
        logger.info(
            "   -> ✅ AI Constitutionalist provided a valid reconciliation plan."
        )
        return reconciliation_result
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"❌ Failed to parse reconciliation plan from AI: {e}")
        logger.error(f"   -> AI Raw Response: {response}")
        return {
            "code_modifications": refactoring_plan,
            "constitutional_amendment_proposal": None,
        }


async def _async_complexity_outliers(
    cognitive_service: CognitiveService, file_path: Path | None, dry_run: bool
):
    """Async core logic for identifying and refactoring complexity outliers."""
    logger.info("🩺 Starting complexity outlier analysis and refactoring cycle...")
    outlier_files: list[str] = (
        [str(file_path.relative_to(REPO_ROOT))] if file_path else []
    )
    if not outlier_files:
        logger.error("❌ Please provide a specific file path to refactor.")
        return
    for file_rel_path in outlier_files:
        try:
            logger.info(f"--- Processing: {file_rel_path} ---")
            source_code = (REPO_ROOT / file_rel_path).read_text(encoding="utf-8")
            logger.info("🧠 Asking RefactoringArchitect for a plan...")
            prompt_template = (
                (settings.MIND / "prompts" / "refactor_outlier.prompt")
                .read_text(encoding="utf-8")
                .replace("{source_code}", source_code)
            )
            refactor_client = await cognitive_service.aget_client_for_role(
                "RefactoringArchitect"
            )
            response = await refactor_client.make_request_async(
                prompt_template, user_id="refactoring_agent"
            )
            refactoring_plan = parse_write_blocks(response)
            if not refactoring_plan:
                raise ValueError(
                    "No valid [[write:]] blocks found in the refactoring plan response."
                )
            logger.info("🔬 Validating generated code for constitutional compliance...")
            auditor_context = AuditorContext(REPO_ROOT)
            validated_code_plan = {}
            for path, code in refactoring_plan.items():
                result = await validate_code_async(
                    path, str(code), auditor_context=auditor_context
                )
                if result["status"] == "dirty":
                    raise Exception(f"Validation FAILED for proposed file '{path}'")
                validated_code_plan[path] = result["code"]
            logger.info("   -> ✅ Plan is valid and formatted.")
            final_code_to_write = validated_code_plan
            if dry_run:
                console.print(
                    Panel(
                        f"Refactoring Plan for [bold cyan]{file_rel_path}[/bold cyan]",
                        expand=False,
                    )
                )
                for path in final_code_to_write:
                    console.print(
                        f"  📄 [yellow]Action:[/yellow] Write to [bold]{path}[/bold]"
                    )
                logger.warning("💧 Dry Run: Skipping write. Plan is valid.")
                continue
            logger.info("💾 Applying validated and formatted refactoring...")
            (REPO_ROOT / file_rel_path).unlink()
            for path, code in final_code_to_write.items():
                (REPO_ROOT / path).write_text(code, encoding="utf-8")
            logger.info(
                "✅ Refactoring applied. Run 'make check' to validate the new code state and fix any manifest drift."
            )
        except Exception as e:
            logger.error(f"❌ Failed to process '{file_rel_path}': {e}", exc_info=True)
            continue


# ID: 453e06ba-139f-427c-bbe3-ff590640b766
def complexity_outliers(
    context: CoreContext,
    file_path: Path | None = typer.Argument(
        None,
        help="Optional: The path to a specific file to refactor. If omitted, outliers are detected automatically.",
        exists=True,
        dir_okay=False,
        resolve_path=True,
    ),
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--write",
        help="Show what refactoring would be applied. Use --write to apply.",
    ),
):
    """Identifies and refactors complexity outliers to improve separation of concerns."""
    asyncio.run(
        _async_complexity_outliers(context.cognitive_service, file_path, dry_run)
    )
