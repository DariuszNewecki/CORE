# src/body/evaluators/atomic_actions_evaluator.py

"""
Atomic Actions Evaluator - AUDIT Phase Component.
Validates code compliance with the atomic actions pattern.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from body.cli.logic.atomic_actions_checker import AtomicActionsChecker
from shared.component_primitive import Component, ComponentPhase, ComponentResult
from shared.config import settings
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 8c95de30-861b-4908-bb93-ab272d4039be
class AtomicActionsEvaluator(Component):
    """
    Evaluates codebase for atomic action pattern compliance.

    Checks:
    - @atomic_action decorator presence
    - ActionResult return types
    - Structured metadata declaration
    """

    @property
    # ID: b73eba23-e6c1-4eb9-930c-dc033915a148
    def phase(self) -> ComponentPhase:
        return ComponentPhase.AUDIT

    # ID: a9bd8873-8696-4f14-a055-a32ba0ecd956
    async def execute(
        self, repo_root: Path | None = None, **kwargs: Any
    ) -> ComponentResult:
        """
        Execute the pattern audit.

        Args:
            repo_root: Optional override for repository root.
        """
        start_time = time.time()
        root = repo_root or settings.REPO_PATH

        # We wrap the existing logic to preserve the complex AST analysis
        # while standardizing the interface.
        checker = AtomicActionsChecker(root)
        legacy_result = checker.check_all()

        # Map legacy violations to component metadata
        violation_dicts = [
            {
                "file": str(v.file_path),
                "function": v.function_name,
                "rule": v.rule_id,
                "message": v.message,
                "severity": v.severity,
                "line": v.line_number,
                "suggested_fix": v.suggested_fix,
            }
            for v in legacy_result.violations
        ]

        duration = time.time() - start_time

        return ComponentResult(
            component_id=self.component_id,
            ok=not legacy_result.has_errors,
            data={
                "total_actions": legacy_result.total_actions,
                "compliant_actions": legacy_result.compliant_actions,
                "compliance_rate": legacy_result.compliance_rate,
                "violations": violation_dicts,
            },
            phase=self.phase,
            confidence=1.0,
            metadata={
                "has_errors": legacy_result.has_errors,
                "violation_count": len(violation_dicts),
            },
            duration_sec=duration,
        )
