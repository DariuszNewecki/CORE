# src/features/self_healing/linelength_service.py
"""
Implements the 'fix line-lengths' command, an AI-powered tool to
refactor code for better readability by adhering to line length policies.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import List, Optional

import typer
from core.cognitive_service import CognitiveService

# --- START OF AMENDMENT: Import the new async validator ---
from core.validation_pipeline import validate_code_async
from rich.progress import track
from shared.config import settings
from shared.logger import getLogger

# --- END OF AMENDMENT ---
from features.governance.audit_context import AuditorContext

log = getLogger("core_admin.fixer_linelength")
REPO_ROOT = settings.REPO_PATH


async def _async_fix_line_lengths(files_to_process: List[Path], dry_run: bool):
    """Async core logic for finding and fixing all line length violations."""
    log.info(
        f"Scanning {len(files_to_process)} files for lines longer than 100 characters..."
    )

    cognitive_service = CognitiveService(REPO_ROOT)
    prompt_template_path = settings.MIND / "prompts" / "fix_line_length.prompt"
    if not prompt_template_path.exists():
        log.error(f"Prompt not found at {prompt_template_path}. Cannot proceed.")
        raise typer.Exit(code=1)
    prompt_template = prompt_template_path.read_text(encoding="utf-8")
    fixer_client = cognitive_service.get_client_for_role("CodeStyleFixer")

    auditor_context = AuditorContext(REPO_ROOT)
    await auditor_context.load_knowledge_graph()  # Pre-load the graph for the validator

    files_with_long_lines = []
    for file_path in files_to_process:
        try:
            for line in file_path.read_text(encoding="utf-8").splitlines():
                if len(line) > 100:
                    files_with_long_lines.append(file_path)
                    break
        except Exception:
            continue

    if not files_with_long_lines:
        log.info("✅ No files with long lines found. Nothing to do.")
        return

    log.info(f"Found {len(files_with_long_lines)} file(s) with long lines to fix.")

    modification_plan = {}

    for file_path in track(
        files_with_long_lines, description="Asking AI to refactor files..."
    ):
        try:
            original_content = file_path.read_text(encoding="utf-8")
            final_prompt = prompt_template.replace("{source_code}", original_content)

            corrected_code = await fixer_client.make_request_async(
                final_prompt, user_id="line_length_fixer_agent"
            )

            if corrected_code and corrected_code.strip() != original_content.strip():
                # --- START OF AMENDMENT: Call the async validator and await it ---
                validation_result = await validate_code_async(
                    str(file_path),
                    corrected_code,
                    quiet=True,
                    auditor_context=auditor_context,
                )
                # --- END OF AMENDMENT ---
                if validation_result["status"] == "clean":
                    modification_plan[file_path] = validation_result["code"]
                else:
                    log.warning(
                        f"Skipping {file_path.name}: AI-generated code failed validation."
                    )
        except Exception as e:
            log.error(f"Could not process {file_path.name}: {e}")

    if dry_run:
        typer.secho("\n💧 Dry Run Summary:", bold=True)
        for file_path in sorted(modification_plan.keys()):
            typer.secho(
                f"  - Would fix line lengths in: {file_path.relative_to(REPO_ROOT)}",
                fg=typer.colors.YELLOW,
            )
    else:
        log.info("\n💾 Writing changes to disk...")
        for file_path, new_code in modification_plan.items():
            file_path.write_text(new_code, "utf-8")
            log.info(
                f"   -> ✅ Fixed line lengths in {file_path.relative_to(REPO_ROOT)}"
            )


# ID: 1655a2ca-f71f-470b-8f43-a33ee28d64dd
def fix_line_lengths(
    file_path: Optional[Path] = typer.Argument(
        None,
        help="Optional: A specific file to fix. If omitted, all project files are scanned.",
        exists=True,
        dir_okay=False,
        resolve_path=True,
    ),
    write: bool = typer.Option(
        False, "--write", help="Apply the changes directly to the files."
    ),
):
    """Uses an AI agent to refactor files with lines longer than 100 characters."""
    files_to_scan = []
    if file_path:
        files_to_scan.append(file_path)
    else:
        # Scan all Python files in the src directory
        src_dir = REPO_ROOT / "src"
        files_to_scan.extend(src_dir.rglob("*.py"))

    asyncio.run(_async_fix_line_lengths(files_to_scan, dry_run=not write))
