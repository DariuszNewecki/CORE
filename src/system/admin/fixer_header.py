# src/system/admin/fixer_header.py
"""
The orchestration logic for the unified header fixer, which uses an LLM
to enforce constitutional style rules on Python file headers.
"""

from __future__ import annotations

from typing import Dict, Optional

import typer
from rich.progress import track

from core.cognitive_service import CognitiveService
from core.validation_pipeline import validate_code
from shared.config import settings
from shared.logger import getLogger
from shared.path_utils import get_repo_root

# --- CHANGE 1: Import the new tool ---
from shared.utils.parallel_processor import ThrottledParallelProcessor

log = getLogger("core_admin.fixer")
REPO_ROOT = get_repo_root()

# CAPABILITY: system.header.fix_cycle


# --- CHANGE 2: The entire function is refactored for clarity and reuse ---
def _run_header_fix_cycle(dry_run: bool, all_py_files: list[str]):
    """The core logic for finding and fixing all header style violations."""
    cognitive_service = CognitiveService(REPO_ROOT)
    prompt_template = (settings.MIND / "prompts" / "fix_header.prompt").read_text(
        encoding="utf-8"
    )
    fixer_client = cognitive_service.get_client_for_role("Coder")

    # Define the async worker function that processes a single file
    async def worker(file_path_str: str) -> Optional[tuple[str, str]]:
        """Async worker that returns (file_path, corrected_code) or None."""
        file_path = REPO_ROOT / file_path_str
        try:
            original_content = file_path.read_text(encoding="utf-8")
            final_prompt = prompt_template.format(
                file_path=file_path_str, source_code=original_content
            )
            corrected_code = await fixer_client.make_request_async(
                final_prompt, user_id="header_fixer_agent"
            )
            if corrected_code and corrected_code.strip() != original_content.strip():
                return (file_path_str, corrected_code)
        except Exception as e:
            log.warning(f"Could not process {file_path_str}: {e}")
        return None

    # Instantiate and run the processor
    processor = ThrottledParallelProcessor(description="Analyzing headers...")
    results = processor.run(all_py_files, worker)

    # Process the results
    modification_plan: Dict[str, str] = {
        file_path: code for file_path, code in filter(None, results)
    }

    if not modification_plan:
        log.info("✅ All file headers are constitutionally compliant.")
        return

    log.info(f"Found {len(modification_plan)} file(s) requiring header fixes.")

    if dry_run:
        typer.secho("💧 Dry Run Summary:", bold=True)
        for file_path in sorted(modification_plan.keys()):
            typer.secho(f"  - Would fix header in: {file_path}", fg=typer.colors.YELLOW)
        return

    log.info("💾 Validating and writing changes to disk...")
    for file_path, new_code in track(modification_plan.items(), "Applying fixes..."):
        validation_result = validate_code(file_path, new_code, quiet=True)
        if validation_result["status"] == "clean":
            (REPO_ROOT / file_path).write_text(validation_result["code"], "utf-8")
        else:
            log.error(
                f"❌ Skipping {file_path} due to validation failure after LLM fix."
            )
