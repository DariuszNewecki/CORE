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

V2.3-REBIRTH SCAFFOLD (2026-06-07):
Named by two constitutional papers as load-bearing for the V2 Adaptive
Workflow Pattern and the V2.3 Limb operational model:
`CORE-V2-Adaptive-Workflow-Pattern.md` §5.5 declares it the constitutional
Orchestrator pattern; `CORE-The-Octopus-UNIX-Synthesis.md` §6 maps it to the
"Pipe coordination" substrate for the Limb. GH #590 closure 1 landed:
`run_adaptive()` now dispatches a component result's `next_suggested` hint
through `_resolve_component(name)`, which combines `discover_components`
(class lookup across `body.analyzers`, `body.evaluators`, `will.strategists`)
with a small per-component DI map mirroring the `ServiceRegistry.get_service`
pattern for services needing `repo_path`. Closure 2 (a concrete Limb command
consuming this dispatch end-to-end) remains deferred: hand-composition is
still the live V2 path (see `will/test_generation/`, `will/self_healing/`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from shared.component_primitive import Component, ComponentResult, discover_components
from shared.infrastructure.intent.operational_config import load_operational_config
from shared.logger import getLogger


logger = getLogger(__name__)

_CFG_EXEC = load_operational_config().execution

_COMPONENT_PACKAGES = (
    "body.analyzers",
    "body.evaluators",
    "will.strategists",
)
"Canonical V2 component packages walked by `_resolve_component`."

_COMPONENTS_NEEDING_REPO_ROOT = frozenset({"constitutionalevaluator"})
"Components whose __init__ requires repo_root injection — mirrors `ServiceRegistry.get_service` line-233 pattern."


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

    def __init__(self, repo_root: Path | None = None):
        """
        Initialize orchestrator with empty state.

        Args:
            repo_root: Optional repo root, threaded into auto-dispatched
                components whose ctor requires it (see
                `_COMPONENTS_NEEDING_REPO_ROOT`). When `run_adaptive` would
                need to dispatch such a component without `repo_root` bound,
                it logs and returns the last result rather than constructing
                with a wrong root.
        """
        self.session_state: dict[str, Any] = {}
        "Accumulated metadata from all components"
        self.execution_history: list[ComponentResult] = []
        "Record of all component executions"
        self.repo_root = repo_root
        self._component_cache: dict[str, type[Component]] | None = None

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
        accumulated_data: dict[str, Any] = {}
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
        max_steps: int = _CFG_EXEC.orchestrator_max_steps,
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
        accumulated_data: dict[str, Any] = {}
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
            try:
                current_component = self._resolve_component(result.next_suggested)
            except (ValueError, TypeError) as exc:
                logger.warning(
                    "Cannot auto-discover next component %r: %s",
                    result.next_suggested,
                    exc,
                )
                return result
            current_inputs = {}
        logger.warning("Reached max_steps (%s), stopping", max_steps)
        return result

    # ID: 5b21f4d3-8e7c-4a91-b16f-9d2e8a4c7b3e
    def _resolve_component(self, name: str) -> Component:
        """
        Construct a fresh component instance by name.

        Used by `run_adaptive()` to materialize a component referenced by
        another component's `next_suggested` hint. Construction handles
        per-component DI via a small allowlist (`_COMPONENTS_NEEDING_REPO_ROOT`);
        names not requiring DI are constructed bare. Raises `ValueError` if
        the name doesn't resolve to a discoverable component, or if the
        component requires DI that the orchestrator wasn't primed with.

        Closure 1 of GH #590.
        """
        if self._component_cache is None:
            cache: dict[str, type[Component]] = {}
            for pkg in _COMPONENT_PACKAGES:
                cache.update(discover_components(pkg))
            self._component_cache = cache
        cls = self._component_cache.get(name)
        if cls is None:
            raise ValueError(
                f"Component {name!r} not found in V2 packages "
                f"({', '.join(_COMPONENT_PACKAGES)})"
            )
        if name in _COMPONENTS_NEEDING_REPO_ROOT:
            if self.repo_root is None:
                raise ValueError(
                    f"Component {name!r} requires repo_root; "
                    f"pass it to ProcessOrchestrator(repo_root=...)"
                )
            return cls(repo_root=self.repo_root)
        return cls()

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
