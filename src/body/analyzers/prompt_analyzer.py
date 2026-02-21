# src/body/analyzers/prompt_analyzer.py
# ID: 230dbdcb-b444-4078-8241-094f785b6e85

"""
Prompt Analyzer - PARSE Phase Component.
Analyzes templates and context to ensure generation tasks are "Ready to Build."

Constitutional Alignment:
- Phase: PARSE (Template validation and analysis)
- Authority: CODE (Implementation)
- Boundary: Requires prompt_root via dependency injection (no settings access)
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

from body.analyzers.base_analyzer import BaseAnalyzer
from shared.component_primitive import ComponentResult  # Component, ComponentPhase,
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: ebe63608-68fb-4f79-9151-c3e940d2d8f2
class PromptAnalyzer(BaseAnalyzer):
    """
    Validates that a generation task has all required variables.

    Responsibilities:
    - Load templates from prompt directory via provided path.
    - Identify required placeholders in the template.
    - Verify that the provided context satisfies those placeholders.
    - Calculate a 'Readiness Score' for the generation task.

    Constitutional Requirement:
    - MUST receive prompt_root parameter (no settings access)
    - Body layer components do not access settings directly
    """

    # ID: 631eec7b-c23d-4d25-8f9f-a191e0239ce9
    async def execute(
        self,
        template_name: str,
        context_data: dict[str, Any],
        prompt_root: Path | None = None,
        **kwargs: Any,
    ) -> ComponentResult:
        """
        Analyze prompt readiness.

        Args:
            template_name: Stem of the prompt file (e.g., 'fix_line_length')
            context_data: Dictionary of variables provided for the prompt.
            prompt_root: Path to prompts directory (required for constitutional compliance)

        Constitutional Compliance:
        - Requires prompt_root parameter (no settings access)
        - Returns error if prompt_root not provided (fail fast, dependency injection enforced)
        """
        start_time = time.time()

        # Constitutional boundary enforcement: Body requires proper parameters
        if prompt_root is None:
            return ComponentResult(
                component_id=self.component_id,
                ok=False,
                data={
                    "error": "PromptAnalyzer requires prompt_root parameter. "
                    "Body layer components must not access settings directly."
                },
                phase=self.phase,
                confidence=0.0,
            )

        try:
            # 1. Load Template via provided prompt_root
            prompt_path = prompt_root / f"{template_name}.txt"
            if not prompt_path.exists():
                return ComponentResult(
                    component_id=self.component_id,
                    ok=False,
                    data={
                        "error": f"Template not found: {template_name} at {prompt_path}"
                    },
                    phase=self.phase,
                    confidence=0.0,
                )

            template_text = prompt_path.read_text(encoding="utf-8")

            # 2. Identify placeholders (e.g., {source_code}, {goal})
            placeholders = set(re.findall(r"\{(\w+)\}", template_text))

            # 3. Cross-reference with provided context
            provided_keys = set(context_data.keys())
            missing_keys = placeholders - provided_keys

            # 4. Calculate Readiness
            # Confidence is 1.0 if all keys present, lower if missing keys.
            confidence = (
                1.0
                if not missing_keys
                else (
                    max(0.0, 1.0 - (len(missing_keys) / len(placeholders)))
                    if placeholders
                    else 1.0
                )
            )

            # 5. Assemble final prompt (if possible)
            # We still produce the string, but now it's an "Analyzed Result"
            final_prompt = None
            if confidence > 0.5:
                # Fill missing keys with warnings so LLM knows context is thin
                safe_context = {**context_data}
                for key in missing_keys:
                    safe_context[key] = (
                        f"[WARNING: Context for '{key}' was not found by Analyzer]"
                    )

                final_prompt = template_text.format(**safe_context)

            duration = time.time() - start_time

            return ComponentResult(
                component_id=self.component_id,
                ok=confidence > 0.8,  # Fail if too much context is missing
                data={
                    "final_prompt": final_prompt,
                    "template_used": str(prompt_path),
                    "required_keys": list(placeholders),
                    "missing_keys": list(missing_keys),
                },
                phase=self.phase,
                confidence=confidence,
                metadata={
                    "readiness": "READY" if not missing_keys else "THIN",
                    "template_name": template_name,
                },
                duration_sec=duration,
            )

        except Exception as e:
            logger.error("PromptAnalyzer failed: %s", e)
            return ComponentResult(
                component_id=self.component_id,
                ok=False,
                data={"error": str(e)},
                phase=self.phase,
                confidence=0.0,
            )
