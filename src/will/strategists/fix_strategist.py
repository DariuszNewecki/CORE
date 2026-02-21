# src/will/strategists/fix_strategist.py

"""
FixStrategist - Prioritizes which fixes to apply first.

Constitutional Alignment:
- Phase: RUNTIME (Deterministic decision-making)
- Authority: POLICY (Applies governance rules for autonomous fixes)
- Tracing: Mandatory DecisionTracer integration
- Purpose: Determine optimal fix sequence and remediation approach

This component determines WHICH fixes to apply and IN WHAT PRIORITY, not HOW to fix them.

Fix Categories:
1. **Critical**: Blocks system functionality (syntax errors, import failures)
2. **High**: Constitutional violations (missing IDs, header compliance)
3. **Medium**: Code quality (complexity, clarity, test coverage)
4. **Low**: Style and formatting (code style, minor issues)

Decision factors: severity, blast radius, auto-fix capability, failure risk, dependencies.
"""

from __future__ import annotations

import time
from typing import Any, ClassVar

from shared.component_primitive import ComponentResult  # Component, ComponentPhase,
from shared.logger import getLogger
from will.orchestration.decision_tracer import DecisionTracer
from will.strategists.base_strategist import BaseStrategist


logger = getLogger(__name__)


# ID: 26539a67-a4e8-4a7a-899e-b133bab02ac0
class FixStrategist(BaseStrategist):
    """
    Decides which fixes to apply and in what order.

    Fix Types:
    - syntax_errors: Critical parsing failures
    - import_errors: Missing or broken imports
    - missing_ids: Constitutional ID requirement violations
    - header_compliance: File header format violations
    - code_style: Black/Ruff formatting issues
    - complexity: High cyclomatic complexity (clarity)
    - test_coverage: Missing or inadequate tests
    - constitutional: Other constitutional violations
    - pattern_compliance: Atomic action pattern violations

    Priority Tiers (Critical → Low):
    1. Critical: syntax_errors, import_errors
    2. High: missing_ids, header_compliance, constitutional
    3. Medium: complexity, test_coverage, pattern_compliance
    4. Low: code_style

    Strategy Selection:
    - emergency: Only critical fixes (syntax/imports)
    - constitutional: Critical + high (governance compliance)
    - quality: Constitutional + medium (add code quality)
    - comprehensive: All fixes in priority order

    Input Requirements:
    - fix_target: str (specific fix type or "all")
    - file_path: str | None (single file vs codebase-wide)
    - severity_threshold: str (critical | high | medium | low)
    - auto_fix_only: bool (skip fixes requiring human review)

    Output:
    - fix_sequence: list[dict] (ordered list with priority/risk)
    - execution_mode: str (sequential | batch)
    - safety_checks: list[str] (required validation steps)
    - estimated_duration_sec: int
    """

    # Fix type definitions with metadata
    FIX_METADATA: ClassVar[dict[str, dict[str, Any]]] = {
        "syntax_errors": {
            "priority": 1,
            "severity": "critical",
            "auto_fixable": False,
            "blast_radius": "file",
            "avg_duration_sec": 5,
        },
        "import_errors": {
            "priority": 1,
            "severity": "critical",
            "auto_fixable": True,
            "blast_radius": "file",
            "avg_duration_sec": 3,
        },
        "missing_ids": {
            "priority": 2,
            "severity": "high",
            "auto_fixable": True,
            "blast_radius": "line",
            "avg_duration_sec": 1,
        },
        "header_compliance": {
            "priority": 2,
            "severity": "high",
            "auto_fixable": True,
            "blast_radius": "file",
            "avg_duration_sec": 2,
        },
        "constitutional": {
            "priority": 2,
            "severity": "high",
            "auto_fixable": False,
            "blast_radius": "varies",
            "avg_duration_sec": 10,
        },
        "complexity": {
            "priority": 3,
            "severity": "medium",
            "auto_fixable": True,  # AI-assisted
            "blast_radius": "function",
            "avg_duration_sec": 30,
        },
        "test_coverage": {
            "priority": 3,
            "severity": "medium",
            "auto_fixable": True,  # AI-generated
            "blast_radius": "file",
            "avg_duration_sec": 45,
        },
        "pattern_compliance": {
            "priority": 3,
            "severity": "medium",
            "auto_fixable": False,
            "blast_radius": "file",
            "avg_duration_sec": 15,
        },
        "code_style": {
            "priority": 4,
            "severity": "low",
            "auto_fixable": True,
            "blast_radius": "file",
            "avg_duration_sec": 2,
        },
    }

    def __init__(self):
        """Initialize strategist with decision tracer."""
        self.tracer = DecisionTracer()

    # ID: 68f07350-e79d-4b00-a5be-8df3a1f1ced5
    async def execute(
        self,
        fix_target: str = "all",
        file_path: str | None = None,
        severity_threshold: str = "low",
        auto_fix_only: bool = False,
        **kwargs: Any,
    ) -> ComponentResult:
        """
        Determine fix execution strategy and priority order.

        Args:
            fix_target: What to fix (specific type or "all")
            file_path: Optional single file target (vs codebase-wide)
            severity_threshold: Minimum severity to include (critical | high | medium | low)
            auto_fix_only: Only include auto-fixable issues
            **kwargs: Additional context (dry_run, previous_failures, etc.)

        Returns:
            ComponentResult with fix strategy and ordered sequence
        """
        start_time = time.time()

        # Normalize inputs
        target = fix_target.lower().strip()
        threshold = severity_threshold.lower().strip()

        # Determine strategy
        strategy = self._select_strategy(
            target, threshold, auto_fix_only, file_path, **kwargs
        )

        # Build fix sequence with prioritization
        fix_sequence = self._build_sequence(
            target, threshold, auto_fix_only, file_path, strategy
        )

        # Filter out non-auto-fixable if requested
        if auto_fix_only:
            fix_sequence = [
                fix for fix in fix_sequence if fix["metadata"]["auto_fixable"]
            ]

        # Determine execution mode
        execution_mode = self._determine_execution_mode(fix_sequence, file_path)

        # Identify required safety checks
        safety_checks = self._identify_safety_checks(fix_sequence, strategy)

        # Estimate duration
        estimated_duration = self._estimate_duration(fix_sequence, file_path)

        # Trace decision for audit trail (Constitutional requirement)
        self.tracer.record(
            agent="FixStrategist",
            decision_type="fix_strategy_selection",
            rationale=(
                f"Selected {strategy} strategy for {target} fixes "
                f"(threshold={threshold}, auto_only={auto_fix_only})"
            ),
            chosen_action=strategy,
            context={
                "fix_target": target,
                "file_path": file_path,
                "severity_threshold": threshold,
                "auto_fix_only": auto_fix_only,
                "fix_sequence": [f["fix_type"] for f in fix_sequence],
                "execution_mode": execution_mode,
                "safety_checks": safety_checks,
                "estimated_duration_sec": estimated_duration,
            },
            confidence=1.0,
        )

        logger.info(
            "FixStrategist: %s strategy → %d fixes (%s mode)",
            strategy,
            len(fix_sequence),
            execution_mode,
        )

        return ComponentResult(
            component_id=self.component_id,
            ok=True,
            phase=self.phase,
            data={
                "strategy": strategy,
                "fix_sequence": fix_sequence,
                "execution_mode": execution_mode,
                "safety_checks": safety_checks,
                "estimated_duration_sec": estimated_duration,
                "fix_target": target,
                "severity_threshold": threshold,
            },
            next_suggested="fix_executor",
            metadata={
                "auto_fix_only": auto_fix_only,
                "file_path": file_path,
                "sequence_length": len(fix_sequence),
                "has_critical_fixes": any(f["priority"] == 1 for f in fix_sequence),
            },
            duration_sec=time.time() - start_time,
        )

    # ID: 3bbb326d-0e4b-4041-9263-0a5ac774c9e2
    def _select_strategy(
        self,
        target: str,
        threshold: str,
        auto_fix_only: bool,
        file_path: str | None,
        **context: Any,
    ) -> str:
        """
        Select fix strategy based on target and constraints.

        Returns: "emergency" | "constitutional" | "quality" | "comprehensive"
        """
        # Emergency: only critical fixes
        if threshold == "critical":
            return "emergency"

        # Constitutional: critical + high priority
        if threshold == "high" or target in ["missing_ids", "header_compliance"]:
            return "constitutional"

        # Quality: constitutional + code quality
        if threshold == "medium" or target in ["complexity", "test_coverage"]:
            return "quality"

        # Comprehensive: everything
        if target == "all" and threshold == "low":
            return "comprehensive"

        # Single file mode is always more targeted
        if file_path:
            return "quality"

        # Default to constitutional (safe default)
        return "constitutional"

    # ID: 1cf76ae1-7524-4ec2-b450-4e54e6475aad
    def _build_sequence(
        self,
        target: str,
        threshold: str,
        auto_fix_only: bool,
        file_path: str | None,
        strategy: str,
    ) -> list[dict[str, Any]]:
        """
        Build prioritized fix sequence.

        Returns: List of fix definitions with metadata
        """
        # Map threshold to priority ceiling
        threshold_priority = {
            "critical": 1,
            "high": 2,
            "medium": 3,
            "low": 4,
        }

        max_priority = threshold_priority.get(threshold, 4)

        # Determine which fix types to include
        if target == "all":
            candidate_fixes = list(self.FIX_METADATA.keys())
        elif target in self.FIX_METADATA:
            candidate_fixes = [target]
        else:
            # Unknown target, use all
            candidate_fixes = list(self.FIX_METADATA.keys())

        # Filter by priority threshold
        sequence = []
        for fix_type in candidate_fixes:
            metadata = self.FIX_METADATA[fix_type]

            # Skip if below threshold
            if metadata["priority"] > max_priority:
                continue

            # Skip if not auto-fixable and auto_only enabled
            if auto_fix_only and not metadata["auto_fixable"]:
                continue

            sequence.append(
                {
                    "fix_type": fix_type,
                    "priority": metadata["priority"],
                    "severity": metadata["severity"],
                    "metadata": metadata,
                }
            )

        # Sort by priority (ascending = higher priority first)
        sequence.sort(key=lambda x: x["priority"])

        return sequence

    # ID: 4f943f26-53dd-4784-b526-cb43ca6cadbf
    def _determine_execution_mode(
        self, fix_sequence: list[dict[str, Any]], file_path: str | None
    ) -> str:
        """
        Decide execution mode based on fixes and scope.

        Returns: "sequential" | "batch"
        """
        # Single file mode is always sequential
        if file_path:
            return "sequential"

        # If all fixes are low-risk and auto-fixable, can batch
        all_low_risk = all(
            fix["metadata"]["blast_radius"] in ["line", "file"]
            and fix["metadata"]["auto_fixable"]
            for fix in fix_sequence
        )

        if all_low_risk and len(fix_sequence) > 3:
            return "batch"

        # Default to sequential for safety
        return "sequential"

    # ID: fc71fb86-1d60-4d3b-ae4f-2fc21b6a95a4
    def _identify_safety_checks(
        self, fix_sequence: list[dict[str, Any]], strategy: str
    ) -> list[str]:
        """
        Identify required safety checks before/after fixes.

        Returns: List of required validation steps
        """
        safety_checks = []

        # Always check syntax after code modifications
        has_code_modifications = any(
            fix["fix_type"] in ["complexity", "clarity", "import_errors"]
            for fix in fix_sequence
        )
        if has_code_modifications:
            safety_checks.append("syntax_validation")

        # Check constitutional compliance after structural changes
        has_structural_changes = any(
            fix["metadata"]["blast_radius"] in ["file", "varies"]
            for fix in fix_sequence
        )
        if has_structural_changes:
            safety_checks.append("constitutional_audit")

        # Check test execution after test generation
        has_test_fixes = any(fix["fix_type"] == "test_coverage" for fix in fix_sequence)
        if has_test_fixes:
            safety_checks.append("test_execution")

        # Check pattern compliance after atomic action fixes
        has_pattern_fixes = any(
            fix["fix_type"] == "pattern_compliance" for fix in fix_sequence
        )
        if has_pattern_fixes:
            safety_checks.append("pattern_validation")

        # Critical strategy requires comprehensive validation
        if strategy == "comprehensive":
            safety_checks.extend(
                ["import_validation", "complexity_check", "coverage_check"]
            )

        # Deduplicate while preserving order
        seen = set()
        unique_checks = []
        for check in safety_checks:
            if check not in seen:
                seen.add(check)
                unique_checks.append(check)

        return unique_checks

    # ID: 7e82e2e7-7e8b-43a7-bb71-dd51b2f03537
    def _estimate_duration(
        self, fix_sequence: list[dict[str, Any]], file_path: str | None
    ) -> int:
        """
        Estimate fix duration in seconds.

        Returns: Estimated duration in seconds
        """
        total = 0

        for fix in fix_sequence:
            base_duration = fix["metadata"]["avg_duration_sec"]

            # Single file is faster than codebase-wide
            if file_path:
                total += base_duration
            else:
                # Multiply by estimated file count (rough heuristic)
                multiplier = {
                    "line": 20,  # ~20 files might need line fixes
                    "file": 10,  # ~10 files might need file-level fixes
                    "function": 15,  # ~15 functions might need refactoring
                    "varies": 30,  # Conservative estimate
                }
                factor = multiplier.get(fix["metadata"]["blast_radius"], 10)
                total += base_duration * factor

        # Add overhead for safety checks (10% of fix time)
        total = int(total * 1.1)

        # Add buffer for sequential execution
        if len(fix_sequence) > 1:
            total += len(fix_sequence) * 2

        return total
