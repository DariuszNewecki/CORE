# src/core/self_correction_engine.py
"""
Self-Correction Engine
This module takes failure context (from validation or test failure)
and attempts to repair the issue using a structured LLM prompt,
then stages the corrected version via the file handler.
"""
import json
from pathlib import Path

from shared.utils.parsing import parse_write_blocks

from core.clients import GeneratorClient
from core.file_handler import FileHandler
from core.prompt_pipeline import PromptPipeline
from core.validation_pipeline import validate_code

REPO_PATH = Path(".").resolve()
pipeline = PromptPipeline(repo_path=REPO_PATH)
file_handler = FileHandler(repo_path=REPO_PATH)


# CAPABILITY: self_correction
def attempt_correction(failure_context: dict) -> dict:
    """Attempts to fix a failed validation or test result by generating corrected code via an LLM prompt based on the provided failure context."""
    """
    Attempts to fix a failed validation or test result using an enriched LLM prompt.
    """
    generator = GeneratorClient()
    file_path = failure_context.get("file_path")
    code = failure_context.get("code")
    # --- MODIFICATION: The key is now "violations", not "error_type" or "details" ---
    violations = failure_context.get("violations", [])
    failure_context.get("original_prompt", "")

    if not file_path or not code or not violations:
        return {
            "status": "error",
            "message": "Missing required failure context fields.",
        }

    # --- MODIFICATION: The prompt is updated to send structured violation data to the LLM ---
    correction_prompt = (
        f"You are CORE's self-correction agent.\n\nA recent code generation attempt failed validation.\n"
        f"Please analyze the violations and fix the code below.\n\nFile: {file_path}\n\n"
        f"[[violations]]\n{json.dumps(violations, indent=2)}\n[[/violations]]\n\n"
        f"[[code]]\n{code.strip()}\n[[/code]]\n\n"
        f"Respond with the full, corrected code in a single write block:\n[[write:{file_path}]]\n<corrected code here>\n[[/write]]"
    )

    final_prompt = pipeline.process(correction_prompt)
    llm_output = generator.make_request(final_prompt, user_id="auto_repair")

    write_blocks = parse_write_blocks(llm_output)

    if not write_blocks:
        return {
            "status": "error",
            "message": "LLM did not produce a valid correction in a write block.",
        }

    # Assuming one write block for self-correction
    path, fixed_code = list(write_blocks.items())[0]

    validation_result = validate_code(path, fixed_code)
    # --- MODIFICATION: Check for 'error' severity in the new violations list ---
    if validation_result["status"] == "dirty":
        return {
            "status": "correction_failed_validation",
            "message": "The corrected code still fails validation.",
            "violations": validation_result["violations"],
        }

    pending_id = file_handler.add_pending_write(
        prompt=final_prompt, suggested_path=path, code=validation_result["code"]
    )
    return {
        "status": "retry_staged",
        "pending_id": pending_id,
        "file_path": path,
        "message": "Corrected code staged for approval.",
    }
