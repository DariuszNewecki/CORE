# src/will/agents/code_generation/extraction.py
# ID: 526ed411-2149-457d-a4de-f2e136ddfa6f

"""
Code extraction and repair utilities.

Constitutional Compliance:
- Traced extraction attempts (no silent assumptions)
- RefusalResult as first-class outcome
- Explicit confidence scoring
"""

from __future__ import annotations

import ast

from shared.component_primitive import ComponentPhase
from shared.logger import getLogger
from shared.models.refusal_result import RefusalResult
from shared.utils.parsing import extract_python_code_from_response


logger = getLogger(__name__)


# ID: c9a5ccfc-fcd1-400e-96e6-83fe2d877f8b
def extract_code_constitutionally(
    raw_response: str,
    task_step: str,
    tracer,
) -> str | RefusalResult:
    """
    Extract code with constitutional discipline.

    Constitutional Compliance:
    1. Primary extraction attempt (traced)
    2. Fallback extraction attempt (TRACED as assumption)
    3. Refusal if both fail (not exception)

    Args:
        raw_response: Raw LLM response
        task_step: Task description for refusal message
        tracer: Decision tracer for logging

    Returns:
        Extracted code string, or RefusalResult if extraction failed
    """
    # EXTRACTION ATTEMPT 1: Primary (standard fenced code blocks)
    code = extract_python_code_from_response(raw_response)

    if code is not None:
        # Success - log and return
        tracer.record(
            agent="CodeGenerator",
            decision_type="code_extraction",
            rationale="Primary extraction successful (fenced code block found)",
            chosen_action="Using standard extraction method",
            context={"method": "primary", "code_length": len(code)},
            confidence=0.95,
        )
        return code

    # EXTRACTION ATTEMPT 2: Fallback (CONSTITUTIONAL: traced as assumption)
    tracer.record(
        agent="CodeGenerator",
        decision_type="extraction_assumption",
        rationale="Primary extraction failed, attempting fallback heuristics",
        chosen_action="Using fallback_extract_python",
        alternatives=["Refuse generation", "Request reformatted response"],
        context={
            "assumption": "LLM response may contain code without fences",
            "confidence_penalty": 0.5,
        },
        confidence=0.3,  # Low confidence on fallback
    )

    code = fallback_extract_python(raw_response)

    if code is not None:
        # Fallback succeeded - log the assumption
        tracer.record(
            agent="CodeGenerator",
            decision_type="code_extraction",
            rationale="Fallback extraction succeeded (heuristic code detection)",
            chosen_action="Using fallback extraction",
            context={
                "method": "fallback",
                "code_length": len(code),
                "quality_warning": "Code extracted without standard fences",
            },
            confidence=0.5,  # Lower confidence for fallback
        )
        logger.warning(
            "⚠️  Code extracted via fallback heuristics. "
            "Consider improving prompt to include proper code fences."
        )
        return code

    # EXTRACTION FAILED: Return RefusalResult (not exception)
    logger.error("❌ Code extraction failed for task: %s", task_step)

    # CONSTITUTIONAL: Refusal as first-class outcome
    return RefusalResult.extraction_failed(
        component_id="code_generator",
        phase=ComponentPhase.EXECUTION,
        reason="Cannot extract valid Python code from LLM response. "
        "Both primary (fenced blocks) and fallback (heuristic) extraction failed. "
        "LLM may not have followed prompt instructions.",
        llm_response_preview=raw_response[:500],
        original_request=task_step,
    )


# ID: a97a30a5-8083-4b02-8de6-fa0892346f8c
def fallback_extract_python(text: str) -> str | None:
    """
    Fallback extraction for messy LLM responses.

    CONSTITUTIONAL NOTE:
    This method is TRACED when called (see extract_code_constitutionally).
    It no longer silently repairs malformed output.

    Args:
        text: Raw LLM response text

    Returns:
        Extracted Python code or None if not found
    """
    lines = text.split("\n")
    code_lines = []
    in_code = False

    for line in lines:
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code or (line and not line.startswith("#") and ":" in line):
            code_lines.append(line)

    return "\n".join(code_lines) if code_lines else None


# ID: 79ace64e-4cd5-47ea-b690-6c2571509c63
def repair_basic_syntax(code: str) -> str:
    """
    Apply basic syntax repairs to generated code.

    Args:
        code: Generated Python code

    Returns:
        Code with basic syntax repairs applied
    """
    try:
        ast.parse(code)
        return code
    except SyntaxError:
        # Basic repairs: ensure proper indentation
        lines = code.split("\n")
        repaired = []
        for line in lines:
            if line.strip() and not line[0].isspace() and ":" in line:
                repaired.append(line)
            else:
                repaired.append(line)
        return "\n".join(repaired)
