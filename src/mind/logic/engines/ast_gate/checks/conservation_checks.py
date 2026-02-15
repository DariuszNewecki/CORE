# src/mind/logic/engines/ast_gate/checks/conservation_checks.py
# ID: 7d6c5b4a-3e2f-41d0-9a8b-7c6d5e4f3a2b

"""
Logic Conservation Checks.
Prevents 'Logic Evaporation' during autonomous refactoring.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 6807cb4f-00d8-429f-b4e0-8970a866fec5
class ConservationChecks:
    """
    Enforces that logic is preserved during transformations.
    """

    @staticmethod
    # ID: 2e3a5e67-17c7-4c86-ad55-b4b3c2d1e0f9
    def check_logic_conservation(
        file_path: Path, current_source: str, params: dict[str, Any]
    ) -> list[str]:
        """
        Compares the size/density of the new code against the original on disk.
        """
        violations = []

        # 1. Parameter extraction
        # Default: flag if more than 50% of the code is deleted
        min_ratio = float(params.get("min_ratio", 0.5))

        # 2. Historical Truth (Physical Disk)
        # Since the 'current_source' passed to the engine usually comes from
        # the LimbWorkspace (Shadow Truth), the file on the physical disk
        # is our 'Historical Truth'.
        if not file_path.exists():
            return []  # New file, nothing to conserve

        original_source = file_path.read_text(encoding="utf-8")

        # 3. Measurement (Character count ignoring whitespace)
        def _get_density(text: str) -> int:
            return len("".join(text.split()))

        orig_density = _get_density(original_source)
        new_density = _get_density(current_source)

        if orig_density == 0:
            return []

        ratio = new_density / orig_density

        # 4. Decision
        if ratio < min_ratio:
            # Constitutional Violation: Logic Evaporation
            reduction_pct = (1 - ratio) * 100
            violations.append(
                f"LOGIC EVAPORATION DETECTED: Code density reduced by {reduction_pct:.1f}%. "
                f"Threshold: {min_ratio*100:.0f}%. "
                "AI may have deleted domain logic to pass tests."
            )

            logger.warning(
                "Conservation Gate Triggered for %s: Ratio %.2f", file_path.name, ratio
            )

        return violations
