# src/core/self_correction_engine.py
"""
Handles automated correction of code failures by generating and validating LLM-suggested repairs based on structured violation data.
"""

from __future__ import annotations

import json

from core.cognitive_service import CognitiveService
from core.file_handler import FileHandler
from core.prompt_pipeline import PromptPipeline
from core.validation_pipeline import validate_code
from shared.config import settings
from shared.utils.parsing import parse_write_blocks

# Use settings for a consistent repo path
REPO_PATH = settings.REPO_PATH
pipeline = PromptPipeline(repo_path=REPO_PATH)
file_handler = FileHandler(str(REPO_PATH))


# CAPABILITY: self_correction
def attempt_correction(
    failure_context: dict, cognitive_service: CognitiveService
) -> dict:
    """Attempts to fix a failed validation or test result using an enriched LLM prompt."""
    # The generator is now acquired from the service, not instantiated directly.
    # We use the 'Coder' role as it's specialized for writing/fixing code.
    generator = cognitive_service.get_client_for_role("Coder")

    file_path = failure_context.get("file_path")
    code = failure_context.get("code")
    violations = failure_context.get("violations", [])

    if not all([file_path, code, violations]):
        return {
            "status": "error",
            "message": "Missing required failure context fields.",
        }

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

    path, fixed_code = list(write_blocks.items())[0]

    validation_result = validate_code(path, fixed_code)
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
