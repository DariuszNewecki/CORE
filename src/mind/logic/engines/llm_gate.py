# src/mind/logic/engines/llm_gate.py
# ID: cfbb2c03-0bed-4a50-a8fa-83cfda4533d4

"""
Semantic Reasoning Auditor.

CONSTITUTIONAL ALIGNMENT:
- Aligned with 'async.no_manual_loop_run'.
- Promoted to natively async to satisfy the BaseEngine contract.
- Prevents thread-blocking during long-running LLM API calls.
- Complies with ASYNC230 by offloading blocking file reads to threads.

HARDENING (V2.6):
- Uses Protocols to avoid Mind -> Body leakage (P2.2).
- Handles AI failures as 'UNAVAILABLE' for audit truthfulness (P1.3).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .base import BaseEngine, EngineResult


if TYPE_CHECKING:
    from shared.path_resolver import PathResolver
    from shared.protocols.llm import LLMClientProtocol


# ID: 8df9b4cd-934a-4115-8e51-2a57833a77d2
class LLMGateEngine(BaseEngine):
    """
    Semantic Reasoning Auditor.

    Uses LLM reasoning to verify abstract rules (Spirit of the Law).
    This engine is decoupled from the Body layer via LLMClientProtocol.
    """

    engine_id = "llm_gate"

    def __init__(
        self,
        path_resolver: PathResolver,
        llm_client: LLMClientProtocol,
    ):
        self._paths = path_resolver
        self.llm = llm_client
        self._cache: dict[str, EngineResult] = {}

    # ID: 66b7f4b7-72a8-43b9-af11-787c58e20524
    async def verify(
        self,
        file_path: Path,
        params: dict[str, Any],
    ) -> EngineResult:
        """
        Natively async verification.

        Performs semantic analysis via LLM without blocking the event loop.
        """

        instruction = params.get("instruction")
        rationale = params.get("rationale", "No rationale provided.")

        # 1. Read file content safely (ASYNC230 compliant)
        try:
            content = await asyncio.to_thread(
                file_path.read_text,
                encoding="utf-8",
            )
        except Exception as e:
            return EngineResult(
                ok=False,
                message=f"IO Error: {e}",
                violations=[],
                engine_id=self.engine_id,
            )

        # 2. Deduplication via state hashing
        try:
            rel_path = str(file_path.relative_to(self._paths.repo_root))
        except ValueError:
            rel_path = str(file_path)

        state_hash = hashlib.sha256(
            f"{rel_path}{instruction}{content}".encode()
        ).hexdigest()

        if state_hash in self._cache:
            return self._cache[state_hash]

        # 3. Construct Auditor Prompt
        system_prompt = (
            "You are the CORE Constitutional Auditor. Your role is to enforce "
            "system governance. You will be given a RULE, a RATIONALE, and a "
            "PIECE OF CODE. Determine if the code violates the rule. "
            "Be strict but fair."
        )

        user_prompt = (
            f"RULE TO ENFORCE: {instruction}\n"
            f"RATIONALE: {rationale}\n\n"
            f"CODE CONTENT:\n---\n{content}\n---\n\n"
            "Return your finding in STRICT JSON format:\n"
            '{ "violation": boolean, "reasoning": "string", "finding": "string or null" }'
        )

        # 4. Invoke LLM Reasoning (async, via Protocol)
        try:
            response_text = await self.llm.make_request(
                prompt=user_prompt,
                system_prompt=system_prompt,
            )

            result_data = json.loads(response_text)

            is_ok = not result_data.get("violation", False)

            message = (
                "Semantic adherence verified."
                if is_ok
                else f"Semantic Violation: {result_data.get('reasoning')}"
            )

            violations = (
                [result_data.get("finding")]
                if not is_ok and result_data.get("finding")
                else []
            )

            final_result = EngineResult(
                ok=is_ok,
                message=message,
                violations=violations,
                engine_id=self.engine_id,
            )

        except Exception as e:
            # P1.3 HARDENING:
            # If the AI fails, enforcement is unavailable (truthful audit result)
            final_result = EngineResult(
                ok=False,
                message=f"ENFORCEMENT_UNAVAILABLE: LLM Reasoning Failed: {e}",
                violations=["SYSTEM_ERROR_AI_OFFLINE"],
                engine_id=self.engine_id,
            )

        # 5. Cache result to avoid redundant LLM calls
        self._cache[state_hash] = final_result

        return final_result
