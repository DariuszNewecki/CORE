# src/body/evaluators/atomic_actions_evaluator.py
"""Atomic Actions Evaluator - AUDIT Phase Component.

Validates code compliance with the atomic actions pattern.

Constitutional Alignment:
- Phase: AUDIT (Quality assessment and pattern detection)
- Authority: POLICY (Enforces constitutional atomic actions pattern)
- Purpose: Validate atomic action compliance across codebase
- Self-contained: No external checker dependencies

PURIFIED (V2.3.0)
- Removed Will-layer 'DecisionTracer' to satisfy architecture.layers.no_body_to_will.
- Preserves 100% of original AST analysis and validation logic.
- Rationale is now returned in metadata for Will-layer consumption.

This module is the audit orchestration shell. The contract definition
(AtomicActionViolation dataclass, AST predicates, validator functions)
lives in atomic_actions_rules.py. The CLI-facing formatter lives in
atomic_actions_format.py.
"""

from __future__ import annotations

import ast
import time
from pathlib import Path
from typing import Any

from shared.component_primitive import ComponentResult
from shared.logger import getLogger

from .atomic_actions_rules import (
    AtomicActionViolation,
    is_atomic_action_candidate,
    validate_atomic_action,
)
from .base_evaluator import BaseEvaluator


logger = getLogger(__name__)


# ID: 54c63404-6a42-4ec3-9b88-8a039d52d7ec
class AtomicActionsEvaluator(BaseEvaluator):
    """Evaluate codebase for atomic action pattern compliance.

    This is a fully self-contained V2 component with no external dependencies.
    All AST analysis and validation logic is internal to this component
    (split across atomic_actions_rules.py for the contract definition).
    """

    # ID: a9bd8873-8696-4f14-a055-a32ba0ecd956
    async def execute(self, repo_root: Path, **kwargs: Any) -> ComponentResult:
        """Execute the atomic actions compliance audit."""
        start_time = time.time()
        src_dir = repo_root / "src"

        violations: list[AtomicActionViolation] = []
        total_actions = 0

        if not src_dir.exists():
            logger.warning("Source directory not found: %s", src_dir)
            return await self._create_result(
                ok=True,
                data={
                    "total_actions": 0,
                    "compliant_actions": 0,
                    "compliance_rate": 100.0,
                    "violations": [],
                },
                confidence=1.0,
                duration=0.0,
                rationale="Source directory missing; no actions audited.",
            )

        # 1) Sensation: scan all Python files in src/
        for py_file in src_dir.rglob("*.py"):
            # Skip private modules (except __init__.py) and test files
            if py_file.name.startswith("_") and py_file.name != "__init__.py":
                continue
            if "test" in str(py_file):
                continue

            file_violations, file_actions = self._check_file(py_file)
            violations.extend(file_violations)
            total_actions += file_actions

        # 2) Analysis: calculate metrics
        compliant_actions = total_actions - len(
            [v for v in violations if v.severity == "error"]
        )
        compliance_rate = (
            (compliant_actions / total_actions * 100.0) if total_actions > 0 else 100.0
        )
        has_errors = any(v.severity == "error" for v in violations)

        # 3) Decision tracing: preserved logic, moved to metadata
        rationale = (
            f"Audited {total_actions} actions. Compliance: {compliance_rate:.1f}%"
        )

        violation_dicts = [
            {
                "file": str(
                    v.file_path.relative_to(repo_root)
                    if v.file_path.is_absolute()
                    else v.file_path
                ),
                "function": v.function_name,
                "rule": v.rule_id,
                "message": v.message,
                "severity": v.severity,
                "line": v.line_number,
                "suggested_fix": v.suggested_fix,
            }
            for v in violations
        ]

        return await self._create_result(
            ok=not has_errors,
            data={
                "total_actions": total_actions,
                "compliant_actions": compliant_actions,
                "compliance_rate": compliance_rate,
                "violations": violation_dicts,
            },
            confidence=1.0,
            duration=time.time() - start_time,
            rationale=rationale,
        )

    def _check_file(self, file_path: Path) -> tuple[list[AtomicActionViolation], int]:
        """Check a single file for atomic action pattern compliance."""
        violations: list[AtomicActionViolation] = []
        action_count = 0

        try:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source)

            for node in ast.walk(tree):
                if isinstance(
                    node, ast.AsyncFunctionDef
                ) and is_atomic_action_candidate(node):
                    action_count += 1
                    violations.extend(validate_atomic_action(file_path, node, source))

        except SyntaxError as e:
            violations.append(
                AtomicActionViolation(
                    file_path=file_path,
                    function_name="<parse_error>",
                    rule_id="syntax_error",
                    message=f"Syntax error: {e}",
                    severity="error",
                )
            )
        except Exception as e:
            logger.error("Error checking %s: %s", file_path, e, exc_info=True)

        return (violations, action_count)
