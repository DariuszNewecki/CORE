# src/will/strategists/validation_strategist.py

"""
ValidationStrategist - Decides which validation checks to run.

Constitutional Alignment:
- Phase: RUNTIME (Deterministic decision-making)
- Authority: POLICY (Applies validation rules from constitution)
- Tracing: Mandatory DecisionTracer integration
- Purpose: Select appropriate validation strategy based on operation risk

This component determines WHICH validation checks are needed, not HOW to execute them.
Decision factors: file path, operation type, risk tier, historical compliance.
"""

from __future__ import annotations

import time
from typing import Any

from shared.component_primitive import Component, ComponentPhase, ComponentResult
from shared.logger import getLogger
from will.orchestration.decision_tracer import DecisionTracer


logger = getLogger(__name__)


# ID: 8f3a2d1b-4c5e-6f7a-8b9c-0d1e2f3a4b5c
class ValidationStrategist(Component):
    """
    Decides which validation checks to execute based on operation context.

    Strategy Selection:
    - minimal: Quick syntax/import checks (low-risk operations)
    - standard: Full constitutional audit (normal operations)
    - comprehensive: All checks + historical analysis (high-risk operations)
    - critical_path: Constitutional + security + performance (critical infrastructure)

    Input Requirements:
    - operation_type: str (e.g., "refactor", "generate", "fix")
    - file_path: str (for risk classification)
    - risk_tier: str (optional, from governance decision)
    - write_mode: bool (whether changes will be persisted)

    Output:
    - validation_strategy: str (minimal | standard | comprehensive | critical_path)
    - required_checks: list[str] (specific check types to run)
    - quality_threshold: float (minimum passing score 0.0-1.0)
    - enforcement_level: str (advisory | blocking)
    """

    def __init__(self):
        """Initialize strategist with decision tracer."""
        self.tracer = DecisionTracer()

    @property
    # ID: 9c4d5e6f-7a8b-9c0d-1e2f-3a4b5c6d7e8f
    def phase(self) -> ComponentPhase:
        """ValidationStrategist operates in RUNTIME phase."""
        return ComponentPhase.RUNTIME

    # ID: 925fc8b7-c94c-41d8-a73f-5c71c3ae1023
    async def execute(
        self,
        operation_type: str,
        file_path: str | None = None,
        risk_tier: str | None = None,
        write_mode: bool = False,
        **kwargs: Any,
    ) -> ComponentResult:
        """
        Select validation strategy based on operation context.

        Args:
            operation_type: Type of operation (refactor, generate, fix, etc.)
            file_path: Optional target file path for risk assessment
            risk_tier: Optional explicit risk tier (ROUTINE, STANDARD, ELEVATED, CRITICAL)
            write_mode: Whether operation will persist changes
            **kwargs: Additional context (previous_failures, complexity_score, etc.)

        Returns:
            ComponentResult with validation strategy and required checks
        """
        start_time = time.time()

        # Determine risk tier if not provided
        if not risk_tier:
            risk_tier = self._classify_risk(file_path, operation_type, write_mode)

        # Select strategy based on risk and operation type
        strategy = self._select_strategy(
            risk_tier, operation_type, write_mode, **kwargs
        )

        # Map strategy to specific checks
        required_checks = self._map_checks(strategy, operation_type, file_path)

        # Set quality thresholds
        quality_threshold = self._determine_threshold(strategy, risk_tier)

        # Determine enforcement level
        enforcement_level = self._determine_enforcement(strategy, risk_tier, write_mode)

        # Trace decision for audit trail (Constitutional requirement)
        self.tracer.record(
            agent="ValidationStrategist",
            decision_type="validation_strategy_selection",
            rationale=(
                f"Selected {strategy} strategy for {operation_type} operation "
                f"(risk_tier={risk_tier}, write_mode={write_mode})"
            ),
            chosen_action=strategy,
            context={
                "operation_type": operation_type,
                "file_path": file_path,
                "risk_tier": risk_tier,
                "write_mode": write_mode,
                "required_checks": required_checks,
                "quality_threshold": quality_threshold,
                "enforcement_level": enforcement_level,
            },
            confidence=1.0,
        )

        logger.info(
            "ValidationStrategist: %s strategy for %s (tier: %s, enforcement: %s)",
            strategy,
            operation_type,
            risk_tier,
            enforcement_level,
        )

        return ComponentResult(
            component_id=self.component_id,
            ok=True,
            phase=self.phase,
            data={
                "validation_strategy": strategy,
                "required_checks": required_checks,
                "quality_threshold": quality_threshold,
                "enforcement_level": enforcement_level,
                "risk_tier": risk_tier,
            },
            next_suggested="constitutional_evaluator",
            metadata={
                "operation_type": operation_type,
                "file_path": file_path,
                "write_mode": write_mode,
            },
            duration_sec=time.time() - start_time,
        )

    # ID: 566e5551-81d0-48f6-90a1-9abd0a9a27b9
    def _classify_risk(
        self, file_path: str | None, operation_type: str, write_mode: bool
    ) -> str:
        """
        Classify operation risk tier based on context.

        Returns: "ROUTINE" | "STANDARD" | "ELEVATED" | "CRITICAL"
        """
        # Critical paths (constitution, governance, core infrastructure)
        if file_path:
            critical_patterns = [
                ".intent/",
                "src/mind/governance/",
                "src/shared/component_primitive.py",
                "src/shared/config.py",
            ]
            if any(pattern in file_path for pattern in critical_patterns):
                return "CRITICAL"

        # Elevated risk for write operations on existing code
        if write_mode and operation_type in ["refactor", "fix", "generate"]:
            return "ELEVATED"

        # Standard for most operations
        if operation_type in ["refactor", "fix", "generate", "test"]:
            return "STANDARD"

        # Routine for read-only operations
        return "ROUTINE"

    # ID: aec6d7af-c145-42ef-9b5e-1aa67e9fae2b
    def _select_strategy(
        self,
        risk_tier: str,
        operation_type: str,
        write_mode: bool,
        **context: Any,
    ) -> str:
        """
        Select validation strategy based on risk and context.

        Returns: "minimal" | "standard" | "comprehensive" | "critical_path"
        """
        # Critical path operations require comprehensive validation
        if risk_tier == "CRITICAL":
            return "critical_path"

        # Elevated risk operations need comprehensive checks
        if risk_tier == "ELEVATED":
            return "comprehensive"

        # Operations with previous failures need extra scrutiny
        if context.get("previous_failures", 0) > 2:
            return "comprehensive"

        # Standard risk tier uses standard validation
        if risk_tier == "STANDARD":
            return "standard"

        # Routine/read-only operations can use minimal validation
        return "minimal"

    # ID: 047723b5-4dd9-4cb5-870e-92783a8599da
    def _map_checks(
        self, strategy: str, operation_type: str, file_path: str | None
    ) -> list[str]:
        """
        Map validation strategy to specific check types.

        Returns: List of check identifiers to execute
        """
        # Base checks for all strategies
        base_checks = ["syntax_validation", "import_validation"]

        # Strategy-specific checks
        strategy_checks = {
            "minimal": base_checks,
            "standard": [
                *base_checks,
                "constitutional_compliance",
                "pattern_compliance",
                "test_coverage",
            ],
            "comprehensive": [
                *base_checks,
                "constitutional_compliance",
                "pattern_compliance",
                "test_coverage",
                "complexity_analysis",
                "audit_history",
                "alignment_verification",
            ],
            "critical_path": [
                *base_checks,
                "constitutional_compliance",
                "pattern_compliance",
                "test_coverage",
                "complexity_analysis",
                "audit_history",
                "alignment_verification",
                "security_scan",
                "performance_analysis",
                "canary_deployment",
            ],
        }

        checks = strategy_checks.get(strategy, strategy_checks["standard"])

        # Add operation-specific checks
        if operation_type == "test":
            checks.append("test_execution")

        if file_path and "models/" in file_path:
            checks.append("schema_validation")

        return checks

    # ID: 136ab84c-3246-4c9d-8f4e-c209893aee34
    def _determine_threshold(self, strategy: str, risk_tier: str) -> float:
        """
        Determine minimum quality threshold for validation to pass.

        Returns: Float between 0.0 (permissive) and 1.0 (strict)
        """
        thresholds = {
            "minimal": 0.7,
            "standard": 0.8,
            "comprehensive": 0.9,
            "critical_path": 0.95,
        }

        base_threshold = thresholds.get(strategy, 0.8)

        # Increase threshold for critical operations (unless already at max)
        if risk_tier == "CRITICAL" and strategy != "critical_path":
            return min(base_threshold + 0.05, 1.0)

        return base_threshold

    # ID: 5ac4bec3-86d8-4d3b-bf37-2dd80df2f89e
    def _determine_enforcement(
        self, strategy: str, risk_tier: str, write_mode: bool
    ) -> str:
        """
        Determine enforcement level for validation failures.

        Returns: "advisory" | "blocking"
        """
        # Critical operations always block on failure
        if risk_tier == "CRITICAL":
            return "blocking"

        # Write operations should block on validation failure
        if write_mode and strategy in ["comprehensive", "critical_path"]:
            return "blocking"

        # Comprehensive strategy blocks for elevated risk
        if strategy == "comprehensive" and risk_tier == "ELEVATED":
            return "blocking"

        # Standard strategy blocks for write operations
        if strategy == "standard" and write_mode:
            return "blocking"

        # Default: advisory (report but don't block)
        return "advisory"
