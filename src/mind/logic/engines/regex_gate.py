# src/mind/logic/engines/regex_gate.py

"""
Pattern-Based Governance Auditor.

CONSTITUTIONAL ALIGNMENT:
- Aligned with 'async.no_manual_loop_run'.
- Promoted to natively async to satisfy the BaseEngine contract.
- Complies with ASYNC230 by offloading blocking file reads to threads.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any

from .base import BaseEngine, EngineResult


# ID: 76df2589-c0fd-48e3-b359-7c58e1c5ff71
class RegexGateEngine(BaseEngine):
    """
    Pattern-Based Governance Auditor.
    Enforces naming conventions and scans for forbidden patterns (secrets, syntax drift).
    """

    engine_id = "regex_gate"

    # ID: 53cc3e25-0d0c-41a7-8ad3-32f8e6963a1a
    async def verify(self, file_path: Path, params: dict[str, Any]) -> EngineResult:
        """
        Natively async verification.
        Matches the BaseEngine contract to prevent loop-hijacking in orchestrators.
        """
        violations = []

        # FACT 1: Check Filename Naming Conventions
        name_pattern = params.get("naming_pattern")
        if name_pattern:
            if not re.match(name_pattern, file_path.name):
                violations.append(
                    f"Naming Violation: File '{file_path.name}' does not match pattern '{name_pattern}'"
                )

        # FACT 2: Check Content
        try:
            # Use to_thread to prevent blocking the event loop during file I/O.
            content = await asyncio.to_thread(file_path.read_text, encoding="utf-8")
        except Exception as e:
            return EngineResult(
                ok=False,
                message=f"IO Error: {e}",
                violations=[],
                engine_id=self.engine_id,
            )

        # 2a: Forbidden Patterns (Negative Check - e.g., Secrets/PII)
        forbidden = params.get("forbidden_patterns") or params.get("patterns", [])
        if isinstance(forbidden, str):
            forbidden = [forbidden]

        for pattern in forbidden:
            matches = re.finditer(pattern, content, re.MULTILINE)
            for match in matches:
                # Find line number for evidence
                line_no = content.count("\n", 0, match.start()) + 1
                violations.append(
                    f"Forbidden Content [Line {line_no}]: Matched restricted regex '{pattern}'"
                )

        # 2b: Required Patterns (Positive Check - e.g., File Headers)
        required = params.get("required_patterns", [])
        if isinstance(required, str):
            required = [required]

        for pattern in required:
            if not re.search(pattern, content, re.MULTILINE):
                violations.append(
                    f"Missing Required Content: Could not find pattern '{pattern}' in file."
                )

        if not violations:
            return EngineResult(
                ok=True,
                message="Pattern compliance verified.",
                violations=[],
                engine_id=self.engine_id,
            )

        return EngineResult(
            ok=False,
            message=f"Constitutional Violation: {len(violations)} pattern mismatches found.",
            violations=violations,
            engine_id=self.engine_id,
        )
