# src/mind/logic/engines/llm_gate.py

"""
Semantic Reasoning Auditor.

CONSTITUTIONAL ALIGNMENT:
- Aligned with 'async.no_manual_loop_run'.
- Promoted to natively async to satisfy the BaseEngine contract.
- Prevents thread-blocking during long-running LLM API calls.
- Complies with ASYNC230 by offloading blocking file reads to threads.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any

from body.services.llm_client import LLMClient
from shared.config import settings

from .base import BaseEngine, EngineResult


# ID: cfbb2c03-0bed-4a50-a8fa-83cfda4533d4
class LLMGateEngine(BaseEngine):
    """
    Semantic Reasoning Auditor.
    Uses LLM reasoning to verify abstract rules (Spirit of the Law).
    """

    engine_id = "llm_gate"

    def __init__(self, llm_client: LLMClient | None = None):
        # FACT: If no client is provided, we build it from the settings evidence
        if llm_client:
            self.llm = llm_client
        else:
            # Using positional arguments as required by LLMClient.__init__
            self.llm = LLMClient(
                api_url=settings.LLM_API_URL,
                api_key=settings.LLM_API_KEY,
                model_name=settings.LLM_MODEL_NAME,
            )
        self._cache: dict[str, EngineResult] = {}

    # ID: 66b7f4b7-72a8-43b9-af11-787c58e20524
    async def verify(self, file_path: Path, params: dict[str, Any]) -> EngineResult:
        """
        Natively async verification.
        Performs semantic analysis via LLM without blocking the event loop.
        """
        instruction = params.get("instruction")
        rationale = params.get("rationale", "No rationale provided.")

        try:
            # CONSTITUTIONAL FIX (ASYNC230):
            # Use to_thread to prevent blocking the event loop during file I/O.
            content = await asyncio.to_thread(file_path.read_text, encoding="utf-8")
        except Exception as e:
            return EngineResult(
                ok=False,
                message=f"IO Error: {e}",
                violations=[],
                engine_id=self.engine_id,
            )

        # FACT: Deduplication. If the file and instruction haven't changed, skip LLM.
        state_hash = hashlib.sha256(f"{instruction}{content}".encode()).hexdigest()
        if state_hash in self._cache:
            return self._cache[state_hash]

        # 1. Fact: Construct the Auditor Prompt
        system_prompt = (
            "You are the CORE Constitutional Auditor. Your role is to enforce system governance. "
            "You will be given a RULE, a RATIONALE, and a PIECE OF CODE. "
            "Determine if the code violates the rule. Be strict but fair."
        )

        user_prompt = (
            f"RULE TO ENFORCE: {instruction}\n"
            f"RATIONALE: {rationale}\n\n"
            f"CODE CONTENT:\n---\n{content}\n---\n\n"
            "Return your finding in STRICT JSON format:\n"
            '{ "violation": boolean, "reasoning": "string", "finding": "string or null" }'
        )

        # 2. Fact: Invoke Reasoning (Natively Async)
        try:
            # ALIGNED: Using make_request as defined in llm_client.py
            response_text = await self.llm.make_request(
                prompt=user_prompt, system_prompt=system_prompt
            )
            result_data = json.loads(response_text)
        except Exception as e:
            return EngineResult(
                ok=False,
                message=f"LLM Reasoning Failed: {e}",
                violations=[],
                engine_id=self.engine_id,
            )

        # 3. Fact: Transform LLM response into EngineResult
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
            ok=is_ok, message=message, violations=violations, engine_id=self.engine_id
        )

        # Update cache to protect your local resources
        self._cache[state_hash] = final_result
        return final_result
