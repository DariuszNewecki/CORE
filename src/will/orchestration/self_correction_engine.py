# src/will/orchestration/self_correction_engine.py
"""
Handles automated correction of code failures by generating and validating LLM-suggested repairs.
Updated for A3: Scans source code for imports to resolve ImportErrors intelligently.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

from shared.config import settings
from shared.logger import getLogger
from shared.utils.parsing import parse_write_blocks

from will.orchestration.cognitive_service import CognitiveService
from will.orchestration.prompt_pipeline import PromptPipeline
from will.orchestration.validation_pipeline import validate_code_async
from will.tools.symbol_finder import SymbolFinder

if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext

logger = getLogger(__name__)
REPO_PATH = settings.REPO_PATH
pipeline = PromptPipeline(repo_path=REPO_PATH)


def _extract_imports_from_code(code: str) -> set[str]:
    """
    Extracts symbol names being imported in the code.
    Handles:
      from module import Symbol
      import Module
    """
    symbols = set()
    # Matches: from x.y import Z, A as B
    from_pattern = re.compile(r"^\s*from\s+[\w.]+\s+import\s+(.+)$", re.MULTILINE)

    for match in from_pattern.finditer(code):
        imports_str = match.group(1)

        # Strip comments first
        if "#" in imports_str:
            imports_str = imports_str.split("#")[0]

        # Handle "Symbol as Alias" or multiple symbols
        for part in imports_str.split(","):
            part = part.strip()
            if not part:
                continue

            # "Symbol as Alias" -> "Symbol"
            symbol = part.split(" as ")[0].strip()
            if symbol:
                symbols.add(symbol)

    return symbols


# ID: 5eba7afe-5491-4e1c-a4a8-c133c8c51ab0
async def attempt_correction(
    failure_context: dict[str, Any],
    cognitive_service: CognitiveService,
    auditor_context: AuditorContext,
) -> dict[str, Any]:
    """
    Attempts to fix a failed validation or test result using an enriched LLM prompt.
    Now includes deep symbol lookup for ImportErrors by analyzing the code.
    """
    generator = await cognitive_service.aget_client_for_role("Coder")

    file_path = failure_context.get("file_path")
    code = failure_context.get("code")
    violations = failure_context.get("violations", [])
    runtime_error = failure_context.get("runtime_error", "")

    if not all([file_path, code]):
        return {
            "status": "error",
            "message": "Missing required failure context fields (file_path, code).",
        }

    # --- A3 Upgrade: Semantic Symbol Lookup ---
    symbol_hints = ""
    if runtime_error and (
        "ImportError" in runtime_error or "ModuleNotFoundError" in runtime_error
    ):
        logger.info("Import error detected. analyzing code for missing symbols...")
        try:
            finder = SymbolFinder()

            # 1. Get hints from the error message itself (legacy/fallback)
            error_line = next(
                (line for line in runtime_error.split("\n") if "Error" in line),
                runtime_error,
            )
            base_hints = await finder.get_context_for_import_error(error_line)

            # 2. Scan the code for what we are actually trying to import
            imported_symbols = _extract_imports_from_code(code)
            deep_hints = []

            if imported_symbols:
                logger.info(
                    f"Scanning Knowledge Graph for imported symbols: {imported_symbols}"
                )
                for symbol in imported_symbols:
                    # UPDATED: Increased limit from 1 to 3 to give context on ambiguous symbols
                    matches = await finder.find_symbol(symbol, limit=3)
                    for m in matches:
                        deep_hints.append(
                            f"  - Found '{m.name}' in '{m.module}' (Use: {m.import_statement})"
                        )

            # Combine hints
            all_hints_text = base_hints
            if deep_hints:
                all_hints_text += "\n\nFound in Knowledge Graph:\n" + "\n".join(
                    deep_hints
                )

            symbol_hints = all_hints_text
            if symbol_hints:
                logger.info(f"Generated symbol hints: {len(symbol_hints)} chars")

        except Exception as e:
            logger.warning("SymbolFinder failed: %s", e)

    # Construct the prompt
    violations_json = json.dumps(violations, indent=2)

    hint_section = ""
    if symbol_hints:
        hint_section = f"\n# INTELLIGENT HINTS (FROM KNOWLEDGE GRAPH)\n{symbol_hints}\n"

    correction_prompt = (
        f"You are CORE's self-correction agent.\n\n"
        f"A recent code generation attempt failed.\n"
        f"Please analyze the errors and fix the code below.\n\n"
        f"File: {file_path}\n\n"
        f"[[violations]]\n{violations_json}\n[[/violations]]\n\n"
        f"[[runtime_error]]\n{runtime_error}\n[[/runtime_error]]\n"
        f"{hint_section}\n"
        f"[[code]]\n{code.strip()}\n[[/code]]\n\n"
        f"Respond with the full, corrected code in a single write block:\n[[write:{file_path}]]\n<corrected code here>\n[[/write]]"
    )

    final_prompt = pipeline.process(correction_prompt)

    # Handle LLM errors defensively
    try:
        llm_output = await generator.make_request_async(
            final_prompt,
            user_id="auto_repair",
        )
    except Exception as e:
        return {
            "status": "error",
            "message": f"LLM request failed: {str(e)}",
        }

    write_blocks = parse_write_blocks(llm_output)

    if not write_blocks:
        return {
            "status": "error",
            "message": "LLM did not produce a valid correction in a write block.",
        }

    path, fixed_code = list(write_blocks.items())[0]

    # Re-validate the fix
    validation_result = await validate_code_async(
        path, fixed_code, auditor_context=auditor_context
    )

    if validation_result["status"] == "dirty":
        # Return detailed info so we can loop again if needed
        return {
            "status": "correction_failed_validation",
            "message": "The corrected code still fails validation.",
            "violations": validation_result["violations"],
            "code": fixed_code,
        }

    return {
        "status": "success",
        "code": validation_result["code"],
        "message": "Corrected code generated and validated successfully.",
    }
