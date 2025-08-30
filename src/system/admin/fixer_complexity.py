# src/system/admin/fixer_complexity.py
"""
Administrative tool for identifying and refactoring code complexity outliers.
This version includes a "Semantic Capability Reconciliation" step to ensure
that refactoring not only improves the code but also proposes necessary
amendments to the system's constitution.
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import typer
import yaml
from rich.console import Console
from rich.panel import Panel

from core.cognitive_service import CognitiveService
from core.validation_pipeline import validate_code
from shared.config import settings
from shared.logger import getLogger
from shared.utils.parsing import extract_json_from_response

log = getLogger("core_admin.fixer_complexity")
console = Console()
REPO_ROOT = settings.REPO_PATH


def _get_capabilities_from_code(code: str) -> List[str]:
    """A simple parser to extract # CAPABILITY tags from a string of code."""
    return re.findall(r"#\s*CAPABILITY:\s*(\S+)", code)


def _propose_constitutional_amendment(proposal_plan: Dict[str, Any]):
    """Creates a formal proposal file for a constitutional amendment."""
    proposal_dir = REPO_ROOT / ".intent" / "proposals"
    proposal_dir.mkdir(exist_ok=True)

    target_file_name = Path(proposal_plan["target_path"]).stem
    # Generate a unique ID for the proposal file
    proposal_id = str(uuid.uuid4())[:8]
    proposal_filename = f"cr-refactor-{target_file_name}-{proposal_id}.yaml"
    proposal_path = proposal_dir / proposal_filename

    # The content of a proposal file is another YAML structure
    proposal_content = {
        "target_path": proposal_plan["target_path"],
        "action": "replace_file",  # For now, we only support replacing the manifest
        "justification": proposal_plan["justification"],
        "content": yaml.dump(
            proposal_plan["content"], indent=2, default_flow_style=False
        ),
    }

    proposal_path.write_text(
        yaml.dump(proposal_content, indent=2, sort_keys=False), encoding="utf-8"
    )
    log.info(
        f"📄 Constitutional amendment proposed at: {proposal_path.relative_to(REPO_ROOT)}"
    )
    return True


def _run_capability_reconciliation(
    cognitive_service: CognitiveService,
    original_code: str,
    original_capabilities: List[str],
    refactoring_plan: Dict[str, str],
) -> Dict[str, Any]:
    """
    Asks an AI Constitutionalist to analyze the refactoring, re-tag capabilities,
    and propose manifest changes.
    """
    log.info("🏛️  Asking AI Constitutionalist to reconcile capabilities...")

    # We create a JSON string of the refactored code to pass to the prompt
    refactored_code_json = json.dumps(refactoring_plan, indent=2)

    prompt = f"""
You are an expert CORE Constitutionalist. You understand that a good refactoring not only improves code but also clarifies purpose.

The original file provided these capabilities: {original_capabilities}
A refactoring has occurred, resulting in these new files:
{refactored_code_json}

Your task is to perform a semantic analysis and produce a JSON object with two keys: "code_modifications" and "constitutional_amendment_proposal".

1.  **code_modifications**: This should be a JSON object where keys are file paths and values are the complete, final source code WITH the original capabilities correctly re-tagged onto the new functions that now hold that responsibility.

2.  **constitutional_amendment_proposal**: If the refactoring has clarified purpose and new, more atomic capabilities should exist, define a manifest change proposal. If no change is needed, this key should be null. The proposal should have 'target_path', 'justification', and 'content' for the new manifest.

Your entire output must be a single, valid JSON object.
"""

    constitutionalist = cognitive_service.get_client_for_role(
        "Planner"
    )  # Use a strong reasoning model
    response = constitutionalist.make_request(prompt, user_id="constitutionalist_agent")

    try:
        # --- THIS IS THE CORRECTED PART ---
        # Use a smarter function to find the JSON, even if the AI response is messy.
        reconciliation_result = extract_json_from_response(response)
        if not reconciliation_result:
            raise ValueError("No valid JSON object found in the AI's response.")
        # --- END OF CORRECTION ---

        log.info("   -> ✅ AI Constitutionalist provided a valid reconciliation plan.")
        return reconciliation_result
    except (json.JSONDecodeError, ValueError) as e:
        log.error(f"❌ Failed to parse reconciliation plan from AI: {e}")
        log.error(f"   -> AI Raw Response: {response}")
        return {
            "code_modifications": refactoring_plan,
            "constitutional_amendment_proposal": None,
        }


# CAPABILITY: refactor.complexity_outlier
def complexity_outliers(
    file_path: Optional[Path] = typer.Argument(
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
    # (The initial part of the function to find outlier_files remains the same)
    log.info("🩺 Starting complexity outlier analysis and refactoring cycle...")
    outlier_files: List[str] = (
        [str(file_path.relative_to(REPO_ROOT))] if file_path else []
    )
    if not outlier_files:
        # Auto-detection logic here
        pass

    cognitive_service = CognitiveService(REPO_ROOT)

    for file_rel_path in outlier_files:
        try:
            log.info(f"--- Processing: {file_rel_path} ---")
            source_code = (REPO_ROOT / file_rel_path).read_text(encoding="utf-8")
            original_capabilities = _get_capabilities_from_code(source_code)

            # --- STEP 1: GENERATE REFACTORING PLAN ---
            log.info("🧠 Asking RefactoringArchitect for a plan...")
            # (Logic for getting refactoring_plan from AI remains the same)
            refactor_prompt = (
                (settings.MIND / "prompts" / "refactor_outlier.prompt")
                .read_text(encoding="utf-8")
                .replace("{source_code}", source_code)
                .replace("{knowledge_graph_summary}", "{}")
            )
            refactor_client = cognitive_service.get_client_for_role(
                "RefactoringArchitect"
            )
            response = refactor_client.make_request(
                refactor_prompt, user_id="refactoring_agent"
            )
            refactoring_plan = json.loads(
                re.search(r"\{.*\}", response, re.DOTALL).group(0)
            )

            # --- STEP 2: VALIDATE & FORMAT PLAN ---
            log.info("🔬 Validating generated code for constitutional compliance...")
            validated_code_plan = {}
            for path, code in refactoring_plan.items():
                result = validate_code(path, str(code), quiet=True)
                if result["status"] == "dirty":
                    raise Exception(f"Validation FAILED for proposed file '{path}'")
                validated_code_plan[path] = result["code"]
            log.info("   -> ✅ Plan is valid and formatted.")

            # --- STEP 3: RECONCILE CAPABILITIES ---
            reconciliation = _run_capability_reconciliation(
                cognitive_service,
                source_code,
                original_capabilities,
                validated_code_plan,
            )
            final_code_to_write = reconciliation.get(
                "code_modifications", validated_code_plan
            )
            amendment_proposal = reconciliation.get("constitutional_amendment_proposal")

            # --- STEP 4: WRITE OR DRY-RUN ---
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
                if amendment_proposal:
                    console.print(
                        f"  🏛️  [yellow]Action:[/yellow] Propose constitutional amendment for [bold]{amendment_proposal['target_path']}[/bold]"
                    )
                log.warning("💧 Dry Run: Skipping write. Plan is valid.")
                continue

            log.info("💾 Applying validated and formatted refactoring...")
            for path, code in final_code_to_write.items():
                (REPO_ROOT / path).write_text(code, encoding="utf-8")

            # --- STEP 5: PROPOSE CONSTITUTIONAL AMENDMENT ---
            if amendment_proposal:
                _propose_constitutional_amendment(amendment_proposal)
                log.info(
                    "✅ Refactoring applied. A constitutional amendment has been proposed."
                )
                log.info(
                    "   Run 'core-admin proposals-list' to see it, and 'make check' to validate the new code state."
                )
            else:
                log.info(
                    "✅ Refactoring applied. No constitutional changes were needed. Run 'make check' to validate."
                )

        except Exception as e:
            log.error(f"❌ Failed to process '{file_rel_path}': {e}", exc_info=True)
            continue
