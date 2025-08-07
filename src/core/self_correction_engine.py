# src/core/self_correction_engine.py
"""
Self-Correction Engine
This module takes failure context (from validation or test failure)
and attempts to repair the issue using a structured LLM prompt,
then stages the corrected version via the file handler.
"""
import json
from pathlib import Path
from core.prompt_pipeline import PromptPipeline
from core.clients import GeneratorClient
from core.validation_pipeline import validate_code
from shared.utils.parsing import parse_write_blocks
from core.file_handler import FileHandler

REPO_PATH = Path(".").resolve()
pipeline = PromptPipeline(repo_path=REPO_PATH)
file_handler = FileHandler(repo_path=REPO_PATH)

# CAPABILITY: self_correction
def attempt_correction(failure_context: dict) -> dict:
    """
    Attempts to fix a failed validation or test result using an enriched LLM prompt.
    """
    generator = GeneratorClient()
    file_path = failure_context.get("file_path")
    code = failure_context.get("code")
    error_type = failure_context.get("error_type")
    details = failure_context.get("details", {})
    base_prompt = failure_context.get("original_prompt", "")

    if not file_path or not code or not error_type:
        return {"status": "error", "message": "Missing required failure context fields."}

    correction_prompt = (
        f"You are CORE's self-correction agent.\n\nA recent code generation attempt failed {error_type}.\n"
        f"Please analyze and fix the code below.\n\nFile: {file_path}\n\n"
        f"[[failure_reason]]\n{json.dumps(details, indent=2)}\n[[/failure_reason]]\n\n"
        f"[[code]]\n{code.strip()}\n[[/code]]\n\n"
        f"Respond with corrected content using the format:\n[[write:{file_path}]]\n<corrected code here>\n[[/write]]"
    )

    final_prompt = pipeline.process(correction_prompt)
    llm_output = generator.make_request(final_prompt, user_id="auto_repair")
    
    write_blocks = parse_write_blocks(llm_output)

    if not write_blocks:
        return {"status": "error", "message": "LLM did not produce valid correction."}

    # Assuming one write block for self-correction
    path, fixed_code = list(write_blocks.items())[0]

    validation = validate_code(path, fixed_code)
    if validation["status"] != "clean":
        return {
            "status": "validation_failed",
            "message": "Corrected code still fails validation.",
            "errors": validation.get("errors", []),
        }

    pending_id = file_handler.add_pending_write(prompt=final_prompt, suggested_path=path, code=validation["code"])
    return {
        "status": "retry_staged",
        "pending_id": pending_id,
        "file_path": path,
        "message": "Corrected code staged for approval.",
    }