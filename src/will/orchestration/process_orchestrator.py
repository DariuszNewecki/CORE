# src/will/orchestration/process_orchestrator.py

"""
Process Orchestrator - Optional workflow coordinator.

Constitutional Alignment:
- Phase: META (coordinates other phases)
- UNIX philosophy: Pipes components together
- Optional: Components work standalone without this

Purpose:
Provides do → evaluate → decide → do workflow pattern.
Accumulates state across components, enables intelligent chaining.

Usage:
    # Create orchestrator
    orch = ProcessOrchestrator()

    # Run sequence
    results = await orch.run_sequence([
        (FileAnalyzer(), {"file_path": path}),
        (TestStrategist(), {}),  # Uses data from previous step
        (TestGenerator(), {}),   # Uses accumulated data
    ])

    # Or run adaptive workflow
    result = await orch.run_adaptive(
        initial_component=FileAnalyzer(),
        initial_inputs={"file_path": path},
        max_steps=10
    )
"""

from __future__ import annotations

from typing import Any

from shared.component_primitive import Component, ComponentResult
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: df9c497f-3746-40e3-b42e-620bf1c07842
class ProcessOrchestrator:
    """
    Coordinates component execution with state accumulation.

    Features:
    - Pipes component outputs to next component inputs
    - Accumulates metadata/state across workflow
    - Supports adaptive workflows (follow next_suggested)
    - Provides evaluation points between steps
    """

    def __init__(self):
        """Initialize orchestrator with empty state."""
        self.session_state: dict[str, Any] = {}
        "Accumulated metadata from all components"
        self.execution_history: list[ComponentResult] = []
        "Record of all component executions"

    # ID: c275895d-4a3b-491b-b7ee-748fe595507e
    async def run_sequence(
        self,
        steps: list[tuple[Component, dict[str, Any]]],
        stop_on_failure: bool = False,
    ) -> list[ComponentResult]:
        """
        Run components in sequence, piping data forward.

        Args:
            steps: List of (component, inputs) tuples
            stop_on_failure: If True, stop on first failure

        Returns:
            List of ComponentResults in execution order

        Example:
            results = await orch.run_sequence([
                (FileAnalyzer(), {"file_path": "src/models.py"}),
                (SymbolExtractor(), {"file_path": "src/models.py"}),
                (TestStrategist(), {}),  # Uses accumulated data
            ])
        """
        results = []
        accumulated_data = {}
        for i, (component, inputs) in enumerate(steps, 1):
            logger.info(
                "Step %s/%s: Executing %s", i, len(steps), component.component_id
            )
            full_inputs = {**accumulated_data, **inputs}
            full_inputs["session_state"] = self.session_state
            result = await component.execute(**full_inputs)
            results.append(result)
            self.execution_history.append(result)
            logger.info(
                "  → %s: ok=%s, confidence=%s",
                component.component_id,
                result.ok,
                result.confidence,
            )
            if not result.ok:
                logger.warning("  → Component failed: %s", result.data.get("error"))
                if stop_on_failure:
                    logger.info("Stopping workflow due to failure")
                    break
            accumulated_data.update(result.data)
            self.session_state.update(result.metadata)
        return results

    # ID: 7461a6ee-2c00-4b21-bc2c-cd03a6d1d2f6
    async def run_adaptive(
        self,
        initial_component: Component,
        initial_inputs: dict[str, Any],
        max_steps: int = 10,
        confidence_threshold: float = 0.3,
    ) -> ComponentResult:
        """
        Run adaptive workflow following next_suggested hints.

        Workflow:
        1. Execute component
        2. Evaluate result
        3. Decide next action based on next_suggested
        4. Repeat until done or max_steps

        Args:
            initial_component: First component to run
            initial_inputs: Initial input data
            max_steps: Maximum steps to prevent infinite loops
            confidence_threshold: Stop if confidence drops below this

        Returns:
            Final ComponentResult

        Example:
            result = await orch.run_adaptive(
                initial_component=FileAnalyzer(),
                initial_inputs={"file_path": path},
                max_steps=5
            )
        """
        logger.info("Starting adaptive workflow")
        current_component = initial_component
        current_inputs = initial_inputs
        accumulated_data = {}
        step_count = 0
        while step_count < max_steps:
            step_count += 1
            logger.info(
                "Adaptive step %s/%s: %s",
                step_count,
                max_steps,
                current_component.component_id,
            )
            full_inputs = {**accumulated_data, **current_inputs}
            full_inputs["session_state"] = self.session_state
            result = await current_component.execute(**full_inputs)
            self.execution_history.append(result)
            logger.info(
                "  → ok=%s, confidence=%s, next=%s",
                result.ok,
                result.confidence,
                result.next_suggested or "none",
            )
            accumulated_data.update(result.data)
            self.session_state.update(result.metadata)
            if not result.ok:
                logger.warning("Component failed, stopping adaptive workflow")
                return result
            if result.confidence < confidence_threshold:
                logger.warning(
                    "Confidence %s below threshold %s, stopping",
                    result.confidence,
                    confidence_threshold,
                )
                return result
            if not result.next_suggested:
                logger.info("No next component suggested, workflow complete")
                return result
            logger.warning(
                "Cannot auto-discover next component: %s", result.next_suggested
            )
            return result
        logger.warning("Reached max_steps (%s), stopping", max_steps)
        return result

    # ID: ddbd6436-f139-43bc-80c2-0387e8bdba8b
    def get_workflow_summary(self) -> dict[str, Any]:
        """
        Get summary of workflow execution.

        Returns:
            Dict with execution statistics
        """
        if not self.execution_history:
            return {
                "total_steps": 0,
                "successful_steps": 0,
                "failed_steps": 0,
                "total_duration": 0.0,
                "avg_confidence": 0.0,
            }
        successful = sum(1 for r in self.execution_history if r.ok)
        failed = len(self.execution_history) - successful
        total_duration = sum(r.duration_sec for r in self.execution_history)
        avg_confidence = sum(r.confidence for r in self.execution_history) / len(
            self.execution_history
        )
        return {
            "total_steps": len(self.execution_history),
            "successful_steps": successful,
            "failed_steps": failed,
            "total_duration": total_duration,
            "avg_confidence": avg_confidence,
            "phases_used": list(set(r.phase.value for r in self.execution_history)),
        }

    # ID: 38ec2821-a72b-4959-8153-be96faf223ac
    def reset(self):
        """Reset orchestrator state for new workflow."""
        self.session_state = {}
        self.execution_history = []
        logger.debug("ProcessOrchestrator state reset")


# ID: 1fc08580-7f67-4294-af1b-7e6a5b7bf0d9
def evaluate_workflow_result(
    result: ComponentResult,
    expected_keys: list[str] | None = None,
    min_confidence: float = 0.5,
) -> tuple[bool, str]:
    """
    Helper function to evaluate if a workflow step succeeded.

    Args:
        result: ComponentResult to evaluate
        expected_keys: Optional list of required keys in result.data
        min_confidence: Minimum acceptable confidence

    Returns:
        Tuple of (success, reason)

    Example:
        success, reason = evaluate_workflow_result(
            result,
            expected_keys=["file_type", "complexity"],
            min_confidence=0.7
        )
        if not success:
            logger.error(f"Workflow failed: {reason}")
    """
    if not result.ok:
        return (False, f"Component failed: {result.data.get('error', 'unknown')}")
    if result.confidence < min_confidence:
        return (
            False,
            f"Confidence {result.confidence:.2f} below threshold {min_confidence}",
        )
    if expected_keys:
        missing = [key for key in expected_keys if key not in result.data]
        if missing:
            return (False, f"Missing expected keys: {missing}")
    return (True, "Success")
