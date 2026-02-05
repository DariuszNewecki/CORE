# src/mind/governance/engine_dispatcher.py
"""
Engine dispatch logic for constitutional rule enforcement.

Bridges IntentGuard orchestration with engine-based verification.
"""

from __future__ import annotations

from pathlib import Path

from mind.governance.policy_rule import PolicyRule
from mind.governance.violation_report import ViolationReport
from mind.logic.engines.registry import EngineRegistry
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 5053335d-8a9a-44cc-8ff2-e3ab577d0622
class EngineDispatcher:
    """
    Handles invocation of constitutional engines for rule verification.

    Responsibilities:
    - Validate file accessibility before engine invocation
    - Dispatch to appropriate engine via EngineRegistry
    - Convert engine results to ViolationReports
    - Handle engine failures gracefully (fail-safe)
    """

    @staticmethod
    # ID: 3d3e0fec-2308-40d2-9d04-31e6a791532f
    def invoke_engine(
        rule: PolicyRule, path: Path, path_str: str
    ) -> list[ViolationReport]:
        """
        Invoke constitutional engine for file verification.

        Args:
            rule: Constitutional rule with engine specification
            path: Absolute path to file
            path_str: Repo-relative path string (for reporting)

        Returns:
            List of violations found (empty if compliant)

        Design:
        - Only invokes engines on existing files
        - Non-existent files are skipped (not an engine concern)
        - Engines operate on absolute paths within repo boundary
        - Engine failures are captured and reported as violations
        """
        violations: list[ViolationReport] = []

        # Skip engine verification if file doesn't exist
        # Rules may reference deleted files, moved files, etc.
        if not path.exists():
            logger.debug(
                "Skipping engine '%s' for rule '%s' - file does not exist: %s",
                rule.engine,
                rule.name,
                path_str,
            )
            return violations

        # Skip engine verification for non-files (directories, etc.)
        if not path.is_file():
            logger.debug(
                "Skipping engine '%s' for rule '%s' - not a file: %s",
                rule.engine,
                rule.name,
                path_str,
            )
            return violations

        try:
            # Get engine from registry
            engine = EngineRegistry.get(rule.engine)

            # Invoke engine verification with absolute path
            # Engines are responsible for reading files safely
            params = rule.params or {}
            result = engine.verify(path, params)

            # Convert engine violations to ViolationReports
            if not result.ok:
                for violation_msg in result.violations:
                    violations.append(
                        ViolationReport(
                            rule_name=rule.name,
                            path=path_str,
                            message=f"{rule.description}: {violation_msg}",
                            severity=rule.severity,
                            suggested_fix="",
                            source_policy=rule.source_policy,
                        )
                    )

        except Exception as e:
            # Engine failure: fail-safe by reporting violation
            # This catches config errors, parsing errors, etc.
            logger.error(
                "Engine '%s' failed for rule '%s' on %s: %s",
                rule.engine,
                rule.name,
                path_str,
                e,
            )
            violations.append(
                ViolationReport(
                    rule_name=rule.name,
                    path=path_str,
                    message=f"Engine failure ({rule.engine}): {e}",
                    severity="error",
                    source_policy=rule.source_policy,
                )
            )

        return violations
