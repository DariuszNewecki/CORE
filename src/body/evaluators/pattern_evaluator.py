# src/body/evaluators/pattern_evaluator.py
# ID: 85bcca66-0390-4eaf-96e4-079b626c5b5e

"""
Pattern Evaluator - AUDIT Phase Component.
Validates code against constitutional design patterns (inspect, action, check).
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from body.cli.logic.pattern_checker import PatternChecker
from shared.component_primitive import Component, ComponentPhase, ComponentResult
from shared.config import settings
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: a0631e53-9a66-45db-a96c-9823ece79763
class PatternEvaluator(Component):
    """
    Evaluates codebase for design pattern compliance.

    Checks:
    - Command patterns (inspect vs action)
    - Service patterns
    - Agent patterns
    """

    @property
    # ID: d164ccc9-f4a1-4fba-9ac1-d4bada7e49df
    def phase(self) -> ComponentPhase:
        return ComponentPhase.AUDIT

    # ID: 52fb3e23-ac1b-4bd9-a49d-abb3b750a15a
    async def execute(
        self, category: str = "all", repo_root: Path | None = None, **kwargs: Any
    ) -> ComponentResult:
        """
        Execute the pattern audit.
        """
        start_time = time.time()
        root = repo_root or settings.REPO_PATH

        checker = PatternChecker(root)

        # Run checks based on requested category
        if category == "all":
            legacy_result = checker.check_all()
        else:
            # Wrap category results in a standard result object
            violations = checker.check_category(category)
            legacy_result = type(
                "Result",
                (),
                {
                    "violations": violations,
                    "total_components": len(violations),  # Best effort for partial
                    "compliant": 0,
                    "passed": len(violations) == 0,
                    "compliance_rate": 100.0 if not violations else 0.0,
                },
            )

        # Map legacy violations to component metadata
        violation_dicts = [
            {
                "file": v.file_path,
                "component": v.component_name,
                "pattern": v.expected_pattern,
                "type": v.violation_type,
                "message": v.message,
                "severity": v.severity,
                "line": v.line_number,
            }
            for v in legacy_result.violations
        ]

        duration = time.time() - start_time

        return ComponentResult(
            component_id=self.component_id,
            ok=legacy_result.passed,
            data={
                "total": legacy_result.total_components,
                "compliant": legacy_result.compliant,
                "compliance_rate": legacy_result.compliance_rate,
                "violations": violation_dicts,
            },
            phase=self.phase,
            confidence=1.0,
            metadata={"category": category, "violation_count": len(violation_dicts)},
            duration_sec=duration,
        )
