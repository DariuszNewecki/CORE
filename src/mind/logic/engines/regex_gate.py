# src/mind/logic/engines/regex_gate.py

"""Provides functionality for the regex_gate module."""

from __future__ import annotations

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
    def verify(self, file_path: Path, params: dict[str, Any]) -> EngineResult:
        violations = []

        # FACT 1: Check Filename Naming Conventions
        # Many rules (like code.python_module_naming) apply to the filename, not content.
        name_pattern = params.get("naming_pattern")
        if name_pattern:
            if not re.match(name_pattern, file_path.name):
                violations.append(
                    f"Naming Violation: File '{file_path.name}' does not match pattern '{name_pattern}'"
                )

        # FACT 2: Check Content
        try:
            content = file_path.read_text()
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
