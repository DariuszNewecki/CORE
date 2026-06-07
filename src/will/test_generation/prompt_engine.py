# src/will/test_generation/prompt_engine.py

"""
Constitutional Test Prompt Builder
Purpose: Encapsulates the high-precision prompt construction logic.
"""

from __future__ import annotations

from typing import Any

from shared.component_primitive import ComponentResult


# ID: 79c76676-92aa-49cd-8e45-e1c2ce44a0ad
class ConstitutionalTestPromptBuilder:
    """
    Handles the assembly of 'Strict Focus' prompts for test generation.
    """

    # ID: 6e29b09f-2a57-4658-b19b-5ee223d84e39
    def build(
        self,
        symbol_name: str,
        symbol_code: str,
        dependencies: list[dict],
        similar_symbols: list[dict],
        strategy: ComponentResult,
        file_type: str,
        complexity: str,
        has_db_harness: bool,
        context_packet: dict[str, Any],
        introspection_facts: dict[str, Any] | None = None,
    ) -> str:
        import_path = context_packet.get("problem", {}).get("target_module", "unknown")

        # Extract strategy details
        strategy_approach = "unknown"
        constraints: list[str] = []
        if getattr(strategy, "data", None) and isinstance(strategy.data, dict):
            strategy_approach = str(strategy.data.get("approach", "unknown"))
            raw_constraints = strategy.data.get("constraints", [])
            if isinstance(raw_constraints, list):
                constraints = [str(c) for c in raw_constraints if str(c).strip()]

        parts = []
        parts.append(f"# TASK: Generate Pytest Unit Tests for '{symbol_name}'")
        parts.append(f"# MODULE: {import_path}")
        parts.append("")

        parts.append("## MANDATORY EXECUTION TRACE")
        parts.append(f"Before writing code, analyze '{symbol_name}' line-by-line:")
        parts.append(
            "1. TRUNCATION: If rsplit(' ', 1)[0] is used, the LAST word is always dropped."
        )
        parts.append("2. BLANK LINES: join(['']) returns '', not a newline.")
        # NEW RULE: Prevents hallucinating that regex trims the edges of the string
        parts.append(
            "3. REGEX COLLAPSE: re.sub(r'[ \\t]+', ' ', '  A  ') results in ' A ', NOT 'A'."
        )
        parts.append("")

        parts.append("## CRITICAL RULES")
        parts.append(f"- STRICT FOCUS: Only test '{symbol_name}'.")
        parts.append("- NO MOCKING: This is a pure utility. Use real data strings.")
        parts.append(f"- IMPORT: from {import_path} import {symbol_name}")
        parts.append("- COMPARISONS: ALWAYS use '==' for value assertions.")
        parts.append(
            "  NEVER use the 'is' keyword for comparing strings, lists, or dicts."
        )
        parts.append(
            "- FILE PATHS: When testing file operations, pass the FULL file path, not just basename."
        )

        # BOILERPLATE MANDATE: Fixes the "Missing pytest import" skip
        parts.append("- BOILERPLATE: You MUST include 'import pytest' at the top.")

        # CHARACTER ACCURACY: Fixes the safe_truncate failures
        parts.append(
            "- CHARACTER ACCURACY: ALWAYS use the Unicode Ellipsis '…' (u+2026)."
        )
        parts.append(
            "  NEVER use three literal dots '...' for truncation expectations. It will fail the sandbox."
        )

        # ISOLATION MANDATE: Fixes logical mismatches with default parameters
        parts.append(
            "- ISOLATION: If the function has multiple boolean default parameters,"
        )
        parts.append(
            "  explicitly set ALL parameters in your assertions to avoid side effects"
        )
        parts.append("  from other default behaviors.")

        # ASYNC FUNCTION HANDLING: Fixes missing 'async def' in test functions
        parts.append(
            f"- ASYNC TESTS: Check if '{symbol_name}' is async (starts with 'async def' in TARGET CODE)."
        )
        parts.append(
            "  If YES: ALL test functions that call it MUST be 'async def test_...' too."
        )
        parts.append(
            "  Use 'await' when calling async functions. Add '@pytest.mark.asyncio' decorator if needed."
        )
        parts.append("  If NO: Use regular 'def test_...' functions.")

        if constraints:
            for constraint in constraints:
                parts.append(f"- {constraint.upper()}")

        parts.append("")

        parts.append("## TARGET CODE")
        parts.append("```python")
        parts.append(symbol_code)
        parts.append("```")
        parts.append("")

        # #589: GROUND TRUTH section — facts pulled from a live import +
        # AST walk of the target. The LLM cannot hallucinate around these
        # without contradicting introspection it can see in the prompt.
        self._append_ground_truth(parts, symbol_name, introspection_facts)

        parts.append("## OUTPUT REQUIREMENTS")
        parts.append("- Include 'import pytest' and the specific module import.")
        parts.append("- Include a comment explaining the detected return type.")
        parts.append("- Return ONLY the Python test code. No fences. No prose.")

        return "\n".join(parts)

    # ID: 3d4e5f6a-7b8c-9d0e-1f2a-3b4c5d6e7f8a
    def _append_ground_truth(
        self,
        parts: list[str],
        symbol_name: str,
        facts: dict[str, Any] | None,
    ) -> None:
        """Emit a ``## GROUND TRUTH`` section derived from live introspection.

        Skipped entirely when ``facts`` is None or carries an
        ``introspection_error`` — the rest of the prompt (TARGET CODE,
        CRITICAL RULES, etc.) still drives generation; we just don't add
        introspection-derived constraints we can't ground.
        """
        if not facts:
            return
        if facts.get("introspection_error"):
            return

        signature = facts.get("signature", "")
        kind = facts.get("kind", "unknown")
        public_attrs = facts.get("public_attrs", [])
        awaited = facts.get("awaited_call_sites", [])
        decorators = facts.get("decorators", [])
        has_gov = facts.get("has_governance_decorator", False)
        is_async = facts.get("is_async", False)

        parts.append(
            "## GROUND TRUTH (live introspection of the target — do NOT contradict)"
        )
        if signature:
            parts.append(f"- Signature: `{symbol_name}{signature}`")
        parts.append(f"- Kind: {kind}{' (async)' if is_async else ''}")
        if kind == "class" and public_attrs:
            # Cap the list so very large public surfaces don't dominate
            # the prompt budget; the most-likely-to-be-tested members
            # are at the top of dir() in alphabetical order.
            head = public_attrs[:30]
            tail = (
                f" (+ {len(public_attrs) - 30} more)" if len(public_attrs) > 30 else ""
            )
            parts.append(f"- Public attributes / methods: {head}{tail}")
        if awaited:
            head = awaited[:15]
            tail = f" (+ {len(awaited) - 15} more)" if len(awaited) > 15 else ""
            parts.append(f"- Awaited call sites in source body: {head}{tail}")
        if decorators:
            parts.append(f"- Decorators on target: {decorators[:5]}")
        parts.append("")
        parts.append("### Hard constraints derived from GROUND TRUTH")
        parts.append(
            "- DO NOT assert on attributes or methods absent from the public-attributes list above."
        )
        parts.append(
            "- The constructor / function MUST be called with arguments matching the Signature above (do not omit required args)."
        )
        if awaited:
            parts.append(
                "- Every awaited call site listed above that your test exercises MUST be backed by an AsyncMock "
                "(not MagicMock — `await MagicMock()` raises TypeError). Patch each at the exact attribute path shown."
            )
        if has_gov:
            parts.append(
                f"- {symbol_name} carries a governance decorator (@atomic_action / @core_command). "
                "Direct calls raise GovernanceBypassError. Call `{symbol_name}.__wrapped__(...)` "
                "or route through ActionExecutor.execute(...), NOT the decorated symbol directly."
            )
        if is_async:
            parts.append(
                "- Target is async. Test functions that call it MUST be `async def test_...` "
                "with `@pytest.mark.asyncio`, and use `await`."
            )
        parts.append("")
