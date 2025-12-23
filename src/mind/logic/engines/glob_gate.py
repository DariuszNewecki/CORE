# src/mind/logic/engines/glob_gate.py

"""Provides functionality for the glob_gate module."""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Any

from .base import BaseEngine, EngineResult


# ID: e9ab205c-263d-40c2-91ce-e44471308a21
class GlobGateEngine(BaseEngine):
    """
    Deterministic Path Auditor.
    Enforces architectural boundaries based on file location and glob patterns.
    """

    engine_id = "glob_gate"

    # ID: 6576f3e8-c1f6-4180-bcd2-076f7cd7a491
    def verify(self, file_path: Path, params: dict[str, Any]) -> EngineResult:
        violations = []

        # Normalize the path relative to project root for consistent matching
        # Assuming project root is where the process runs
        try:
            target_path = str(file_path)
        except Exception as e:
            return EngineResult(
                ok=False,
                message=f"Invalid path: {e}",
                violations=[],
                engine_id=self.engine_id,
            )

        # 1. Fact: Extract patterns from parameters
        # Support 'patterns', 'include', 'forbidden_paths', or 'patterns_prohibited'
        patterns = (
            params.get("patterns")
            or params.get("forbidden_paths")
            or params.get("patterns_prohibited", [])
        )
        if isinstance(patterns, str):
            patterns = [patterns]

        # 2. Fact: Check for pattern matches (The Violation)
        for pattern in patterns:
            if self._match(target_path, pattern):
                action_type = params.get("action", "block")
                violations.append(
                    f"Resource '{target_path}' matches restricted pattern '{pattern}' (Action: {action_type})"
                )

        # 3. Fact: Check Exclusions (Exceptions)
        exceptions = params.get("exceptions", [])
        if violations and exceptions:
            # Filter out violations that are actually exceptions
            violations = [
                v
                for v in violations
                if not any(self._match(target_path, exc) for exc in exceptions)
            ]

        if not violations:
            return EngineResult(
                ok=True,
                message="Path authorization verified.",
                violations=[],
                engine_id=self.engine_id,
            )

        return EngineResult(
            ok=False,
            message="Boundary Violation: Attempted access to protected zone.",
            violations=violations,
            engine_id=self.engine_id,
        )

    def _match(self, path: str, pattern: str) -> bool:
        """
        Implements robust glob matching including recursive (**) support.
        """
        # Convert path to posix style for consistent matching
        path = path.replace("\\", "/")
        pattern = pattern.replace("\\", "/")

        # Standard fnmatch handles * and ?, but not always ** correctly in all versions
        # Here we use the common glob logic:
        if "**" in pattern:
            # Handle recursive globbing by splitting and matching
            parts = pattern.split("/**")
            prefix = parts[0]
            if not prefix:  # pattern was "/**/file.py"
                return path.endswith(parts[1]) if len(parts) > 1 else True
            return path.startswith(prefix)

        return fnmatch.fnmatch(path, pattern)
