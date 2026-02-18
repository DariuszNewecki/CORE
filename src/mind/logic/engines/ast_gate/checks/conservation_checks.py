# src/mind/logic/engines/ast_gate/checks/conservation_checks.py

"""
Logic Conservation Checks - The Anti-Lobotomy Guard.

Prevents "Logic Evaporation" during autonomous refactoring.
Ensures that public symbols (functions/classes) present in the original code
are still present in the new code, or explicitly accounted for.

CONSTITUTIONAL ALIGNMENT:
- Deterministic: Uses AST parsing, not LLM "vibes".
- Safety-First: Defaults to blocking if symbols disappear.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 51adad1f-3844-473f-9487-906669b93b93
class ConservationChecks:
    """
    Enforces that logic is preserved during transformations.
    """

    @staticmethod
    # ID: 6bec4b51-7527-407a-a76c-a1969bf456ac
    def check_logic_conservation(
        file_path: Path, current_source: str, params: dict[str, Any]
    ) -> list[str]:
        """
        Compares the new code against the original on disk.

        Checks:
        1. Code Density (Size sanity check).
        2. Symbol Retention (Did we delete public functions/classes?).
        """
        violations = []

        # 1. Historical Truth (Physical Disk)
        # If file doesn't exist on disk, it's a new file. No conservation needed.
        if not file_path.exists():
            return []

        try:
            original_source = file_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning("Could not read original file for conservation check: %s", e)
            return []

        # --- CHECK 1: DENSITY (The "Sanity Check") ---
        # We keep this as a coarse filter for massive deletions.
        min_ratio = float(params.get("min_ratio", 0.5))

        def _get_density(text: str) -> int:
            return len("".join(text.split()))

        orig_density = _get_density(original_source)
        new_density = _get_density(current_source)

        if orig_density > 0:
            ratio = new_density / orig_density
            if ratio < min_ratio:
                reduction_pct = (1 - ratio) * 100
                violations.append(
                    f"MASS DELETION DETECTED: Code density reduced by {reduction_pct:.1f}%. "
                    f"(Threshold: {min_ratio*100:.0f}%). "
                    "This suggests potential logic evaporation."
                )

        # --- CHECK 2: SYMBOL RETENTION (The "Anti-Lobotomy" Check) ---
        # We must ensure public symbols haven't vanished.

        try:
            orig_symbols = ConservationChecks._extract_public_symbols(original_source)
            new_symbols = ConservationChecks._extract_public_symbols(current_source)

            missing_symbols = orig_symbols - new_symbols

            if missing_symbols:
                # We sort them for deterministic error messages
                missing_list = sorted(list(missing_symbols))
                violations.append(
                    f"SYMBOL LOSS DETECTED: The following public symbols were deleted: {', '.join(missing_list)}. "
                    "Refactoring must preserve existing public interfaces unless explicitly deprecated."
                )

        except SyntaxError:
            # If we can't parse, other checks will catch it.
            # We don't want to double-report syntax errors here.
            pass
        except Exception as e:
            logger.error("Symbol retention check failed: %s", e)

        if violations:
            logger.warning("Conservation Gate Triggered for %s", file_path.name)

        return violations

    @staticmethod
    def _extract_public_symbols(source: str) -> set[str]:
        """
        Parses source and returns a set of public class/function names.
        """
        symbols = set()
        try:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                ):
                    # Ignore private symbols and dunder methods
                    if not node.name.startswith("_"):
                        symbols.add(node.name)
        except SyntaxError:
            # Let the caller handle syntax errors or ignore
            raise

        return symbols
