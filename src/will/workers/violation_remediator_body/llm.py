# src/will/workers/violation_remediator_body/llm.py
"""
LLM invocation for ViolationRemediator.

Responsibility: invoke RemoteCoder via PromptModel, parse and validate
the response. No file writes. No Blackboard writes.
"""

from __future__ import annotations

import json
from typing import Any

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: a7256a38-cbdf-430e-ac84-1fbfe9bb102b
class LLMMixin:
    """
    Mixin providing LLM invocation for ViolationRemediator.

    Requires self._ctx and self._target_rule to be set by the host class.
    """

    async def _invoke_llm(
        self,
        file_path: str,
        source_code: str,
        context_text: str,
        violations_summary: str,
        architectural_context: dict[str, Any],
    ) -> str | None:
        """
        Invoke RemoteCoder (Grok) via PromptModel to produce a fix.

        architectural_context is passed as advisory evidence under the key
        'architectural_context'. The prompt template must treat it as
        context, not as a directive. The LLM's obligation is to satisfy
        the violated rule, not to execute the recommended strategy.
        """
        import ast as _ast

        from shared.ai.prompt_model import PromptModel
        from shared.ai.response_parser import extract_json

        try:
            client = await self._ctx.cognitive_service.aget_client_for_role(
                "RemoteCoder"
            )
            model = PromptModel.load("violation_remediator")
            result = await model.invoke(
                context={
                    "file_path": file_path,
                    "source_code": source_code,
                    "context_package": context_text or "(no additional context)",
                    "violations": violations_summary,
                    # NOTE: architectural_context is advisory evidence only.
                    # It describes detected file role and candidate strategies.
                    # It is NOT a planning directive. The fix must satisfy
                    # the violated rule; the context informs, not commands.
                    "architectural_context": json.dumps(
                        architectural_context, indent=2
                    ),
                    "rule_id": self._target_rule,
                },
                client=client,
                user_id="violation_remediator",
            )

            try:
                parsed = extract_json(result)
            except (json.JSONDecodeError, ValueError) as parse_exc:
                logger.warning(
                    "ViolationRemediator: JSON parse failed for %s - %s\nRaw: %s",
                    file_path,
                    parse_exc,
                    (result or "")[:500],
                )
                return None

            code = parsed.get("code") or ""
            if not code:
                logger.warning(
                    "ViolationRemediator: LLM response missing 'code' field for %s",
                    file_path,
                )
                return None

            try:
                _ast.parse(code)
            except SyntaxError as syn_exc:
                logger.warning(
                    "ViolationRemediator: LLM produced invalid Python for %s - %s\n"
                    "First 200 chars: %s",
                    file_path,
                    syn_exc,
                    code[:200],
                )
                return None

            return code

        except Exception as exc:
            logger.warning(
                "ViolationRemediator: LLM invocation failed for %s - %s",
                file_path,
                exc,
            )
            return None
