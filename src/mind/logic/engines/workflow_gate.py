# src/mind/logic/engines/workflow_gate.py

"""Provides functionality for the workflow_gate module."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .base import BaseEngine, EngineResult


# ID: 170810a6-c446-41de-acf4-29defa345522
class WorkflowGateEngine(BaseEngine):
    """
    Process-Aware Governance Auditor.
    Enforces rules based on the results of workflows (Tests, Coverage, Audits).
    """

    engine_id = "workflow_gate"

    # ID: 449a88ef-71ff-4f63-b692-4cffdc6483ce
    def verify(self, file_path: Path, params: dict[str, Any]) -> EngineResult:
        violations = []

        # FACT: This engine usually requires access to the latest ActionResult or
        # a state artifact (like coverage.json or an entry in the 'audits' table).
        check_type = params.get("check_type")

        if check_type == "test_verification":
            violations.extend(self._verify_tests(params))

        elif check_type == "coverage_minimum":
            violations.extend(self._verify_coverage(params))

        elif check_type == "canary_audit":
            violations.extend(self._verify_canary(params))

        else:
            return EngineResult(
                ok=False,
                message=f"Logic Error: Unknown workflow check type '{check_type}'",
                violations=[],
                engine_id=self.engine_id,
            )

        if not violations:
            return EngineResult(
                ok=True,
                message="Workflow quality requirements met.",
                violations=[],
                engine_id=self.engine_id,
            )

        return EngineResult(
            ok=False,
            message="Quality Gate Failure: Process requirements not satisfied.",
            violations=violations,
            engine_id=self.engine_id,
        )

    def _verify_tests(self, params: dict[str, Any]) -> list[str]:
        """Checks if the most recent test workflow passed."""
        # In a real CORE run, this would query the DB or check a standard artifact.
        # Here we model the logic based on the 'ok' contract.
        last_test_result = params.get("last_action_result", {})

        if not last_test_result.get("ok", False):
            return ["Required test suite failed or has not been run for this context."]
        return []

    def _verify_coverage(self, params: dict[str, Any]) -> list[str]:
        """Checks if code coverage meets the constitutional threshold."""
        threshold = params.get("threshold", 75)  # Default per operations.json
        current_coverage = params.get("current_coverage")

        if current_coverage is None:
            cov_file = Path("coverage.json")
            if cov_file.exists():
                try:
                    data = json.loads(cov_file.read_text())
                    current_coverage = data.get("totals", {}).get("percent_covered", 0)
                except (
                    json.JSONDecodeError,
                    KeyError,
                    Exception,
                ):  # <--- Fixed bare except
                    pass

        if current_coverage is not None and current_coverage < threshold:
            return [
                f"Coverage too low: {current_coverage}% (Constitutional Minimum: {threshold}%)"
            ]

        if current_coverage is None:
            return [
                "No coverage data found. Coverage must be measured before integration."
            ]

        return []

    def _verify_canary(self, params: dict[str, Any]) -> list[str]:
        """Ensures a canary deployment passed in a protected environment."""
        if not params.get("canary_passed", False):
            return [
                "Canary audit required: Operation must pass in staging/isolation first."
            ]
        return []
