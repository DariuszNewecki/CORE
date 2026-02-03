# src/will/strategists/sync_strategist.py

"""
SyncStrategist - Decides sync execution order based on dependencies.

Constitutional Alignment:
- Phase: RUNTIME (Deterministic decision-making)
- Authority: POLICY (Applies data.ssot.database_primacy rules)
- Tracing: Mandatory DecisionTracer integration
- Purpose: Determine optimal sync sequence respecting dependencies

This component determines WHICH syncs to run and IN WHAT ORDER, not HOW to execute them.

Sync Dependency Graph:
    domains → symbols → vectors
    policies → vectors
    patterns → vectors

Decision factors: target scope, dependency ordering, data freshness, failure history.
"""

from __future__ import annotations

import time
from typing import Any

from shared.component_primitive import Component, ComponentPhase, ComponentResult
from shared.logger import getLogger
from will.orchestration.decision_tracer import DecisionTracer


logger = getLogger(__name__)


# ID: 1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d
class SyncStrategist(Component):
    """
    Decides which sync operations to run and in what order.

    Sync Types:
    - domains: Constitutional domain taxonomy (domains.yaml → DB)
    - symbols: Code symbol extraction (src/ → DB)
    - vectors_policies: Policy document embeddings (.intent/phases/, .intent/workflows/ → Qdrant)
    - vectors_patterns: Pattern document embeddings (.intent/enforcement/mappings/ → Qdrant)
    - vectors_symbols: Symbol embeddings (DB → Qdrant)

    Dependency Rules:
    - symbols REQUIRES domains (foreign key)
    - vectors_symbols REQUIRES symbols (source data)
    - vectors_policies INDEPENDENT
    - vectors_patterns INDEPENDENT

    Strategy Selection:
    - minimal: Only sync what's explicitly requested (no dependencies)
    - smart: Sync requested + direct dependencies
    - full: Sync everything in correct order
    - repair: Like full, but force-refresh all data

    Input Requirements:
    - sync_target: str (domains | symbols | vectors | all)
    - force_refresh: bool (whether to re-sync existing data)
    - include_dependencies: bool (whether to auto-include deps)

    Output:
    - sync_sequence: list[str] (ordered list of sync operations)
    - execution_mode: str (parallel | sequential)
    - force_flags: dict[str, bool] (force refresh per operation)
    - estimated_duration_sec: int
    """

    def __init__(self):
        """Initialize strategist with decision tracer."""
        self.tracer = DecisionTracer()

    @property
    # ID: 2b3c4d5e-6f7a-8b9c-0d1e-2f3a4b5c6d7e
    def phase(self) -> ComponentPhase:
        """SyncStrategist operates in RUNTIME phase."""
        return ComponentPhase.RUNTIME

    # ID: 3c4d5e6f-7a8b-9c0d-1e2f-3a4b5c6d7e8f
    async def execute(
        self,
        sync_target: str,
        force_refresh: bool = False,
        include_dependencies: bool = True,
        **kwargs: Any,
    ) -> ComponentResult:
        """
        Determine sync execution strategy and order.

        Args:
            sync_target: What to sync (domains | symbols | vectors | policies | patterns | all)
            force_refresh: Whether to force re-sync of existing data
            include_dependencies: Whether to automatically include dependencies
            **kwargs: Additional context (previous_failures, dry_run, etc.)

        Returns:
            ComponentResult with sync strategy and ordered sequence
        """
        start_time = time.time()

        # Normalize target
        target = sync_target.lower().strip()

        # Validate target
        valid_targets = {
            "domains",
            "symbols",
            "vectors",
            "policies",
            "patterns",
            "all",
        }

        if target not in valid_targets:
            return ComponentResult(
                component_id=self.component_id,
                ok=False,
                phase=self.phase,
                data={
                    "error": f"Invalid sync target: {target}",
                    "valid_targets": list(valid_targets),
                },
                confidence=0.0,
                duration_sec=time.time() - start_time,
            )

        # Determine strategy based on context
        strategy = self._select_strategy(
            target, force_refresh, include_dependencies, **kwargs
        )

        # Build sync sequence respecting dependencies
        sync_sequence = self._build_sequence(target, include_dependencies, strategy)

        # Determine execution mode (parallel vs sequential)
        execution_mode = self._determine_execution_mode(sync_sequence, **kwargs)

        # Configure force flags per operation
        force_flags = self._configure_force_flags(
            sync_sequence, force_refresh, strategy
        )

        # Estimate duration
        estimated_duration = self._estimate_duration(sync_sequence, force_refresh)

        # Trace decision for audit trail (Constitutional requirement)
        self.tracer.record(
            agent="SyncStrategist",
            decision_type="sync_strategy_selection",
            rationale=(
                f"Selected {strategy} strategy for {target} sync "
                f"(include_deps={include_dependencies}, force={force_refresh})"
            ),
            chosen_action=strategy,
            context={
                "sync_target": target,
                "force_refresh": force_refresh,
                "include_dependencies": include_dependencies,
                "sync_sequence": sync_sequence,
                "execution_mode": execution_mode,
                "force_flags": force_flags,
                "estimated_duration_sec": estimated_duration,
            },
            confidence=1.0,
        )

        logger.info(
            "SyncStrategist: %s strategy for %s → %d operations (%s mode)",
            strategy,
            target,
            len(sync_sequence),
            execution_mode,
        )

        return ComponentResult(
            component_id=self.component_id,
            ok=True,
            phase=self.phase,
            data={
                "strategy": strategy,
                "sync_sequence": sync_sequence,
                "execution_mode": execution_mode,
                "force_flags": force_flags,
                "estimated_duration_sec": estimated_duration,
                "sync_target": target,
            },
            next_suggested="sync_executor",
            metadata={
                "include_dependencies": include_dependencies,
                "force_refresh": force_refresh,
                "sequence_length": len(sync_sequence),
            },
            duration_sec=time.time() - start_time,
        )

    # ID: 4d5e6f7a-8b9c-0d1e-2f3a-4b5c6d7e8f9a
    def _select_strategy(
        self,
        target: str,
        force_refresh: bool,
        include_dependencies: bool,
        **context: Any,
    ) -> str:
        """
        Select sync strategy based on target and context.

        Returns: "minimal" | "smart" | "full" | "repair"
        """
        # Repair strategy for force refresh + all
        if force_refresh and target == "all":
            return "repair"

        # Full strategy for "all" target
        if target == "all":
            return "full"

        # Smart strategy when dependencies enabled
        if include_dependencies:
            return "smart"

        # Minimal strategy (just what's requested)
        return "minimal"

    # ID: 5e6f7a8b-9c0d-1e2f-3a4b-5c6d7e8f9a0b
    def _build_sequence(
        self, target: str, include_dependencies: bool, strategy: str
    ) -> list[str]:
        """
        Build ordered sync sequence respecting dependencies.

        Returns: List of sync operation IDs in execution order
        """
        # Define dependency graph
        dependencies = {
            "symbols": ["domains"],  # symbols requires domains
            "vectors_symbols": ["symbols"],  # vector sync requires symbol data
            "vectors_policies": [],  # independent
            "vectors_patterns": [],  # independent
        }

        # Full canonical order (respects all dependencies)
        canonical_order = [
            "domains",
            "symbols",
            "vectors_policies",
            "vectors_patterns",
            "vectors_symbols",
        ]

        # Strategy-specific sequence building
        if strategy == "full" or strategy == "repair":
            return canonical_order

        if strategy == "minimal":
            # Just what was requested, no dependencies
            return self._resolve_target_to_operations(target)

        if strategy == "smart":
            # Requested + dependencies
            requested_ops = self._resolve_target_to_operations(target)
            needed_ops = set(requested_ops)

            # Add dependencies recursively
            for op in requested_ops:
                if op in dependencies:
                    needed_ops.update(dependencies[op])

            # Return in canonical order
            return [op for op in canonical_order if op in needed_ops]

        # Fallback to minimal
        return self._resolve_target_to_operations(target)

    # ID: 6f7a8b9c-0d1e-2f3a-4b5c-6d7e8f9a0b1c
    def _resolve_target_to_operations(self, target: str) -> list[str]:
        """
        Map user-facing target to internal operation IDs.

        Returns: List of operation IDs
        """
        target_map = {
            "domains": ["domains"],
            "symbols": ["symbols"],
            "vectors": ["vectors_policies", "vectors_patterns", "vectors_symbols"],
            "policies": ["vectors_policies"],
            "patterns": ["vectors_patterns"],
            "all": [
                "domains",
                "symbols",
                "vectors_policies",
                "vectors_patterns",
                "vectors_symbols",
            ],
        }

        return target_map.get(target, [target])

    # ID: 7a8b9c0d-1e2f-3a4b-5c6d-7e8f9a0b1c2d
    def _determine_execution_mode(
        self, sync_sequence: list[str], **context: Any
    ) -> str:
        """
        Decide whether syncs can run in parallel or must be sequential.

        Returns: "parallel" | "sequential"
        """
        # Check for dependencies between operations in sequence
        has_dependencies = any(
            op in ["symbols", "vectors_symbols"] for op in sync_sequence
        )

        # If there are dependencies, must run sequential
        if has_dependencies and len(sync_sequence) > 1:
            return "sequential"

        # If all operations are independent (e.g., just vector syncs)
        independent_ops = {"vectors_policies", "vectors_patterns"}
        all_independent = all(op in independent_ops for op in sync_sequence)

        if all_independent and len(sync_sequence) > 1:
            return "parallel"

        # Default to sequential for safety
        return "sequential"

    # ID: 8b9c0d1e-2f3a-4b5c-6d7e-8f9a0b1c2d3e
    def _configure_force_flags(
        self, sync_sequence: list[str], force_refresh: bool, strategy: str
    ) -> dict[str, bool]:
        """
        Determine which operations should force-refresh data.

        Returns: Dict mapping operation ID to force flag
        """
        force_flags = {}

        for op in sync_sequence:
            if strategy == "repair":
                # Repair strategy forces everything
                force_flags[op] = True
            elif force_refresh:
                # Force refresh applies to all operations
                force_flags[op] = True
            else:
                # No force by default
                force_flags[op] = False

        return force_flags

    # ID: 9c0d1e2f-3a4b-5c6d-7e8f-9a0b1c2d3e4f
    def _estimate_duration(self, sync_sequence: list[str], force_refresh: bool) -> int:
        """
        Estimate sync duration in seconds.

        Returns: Estimated duration in seconds
        """
        # Base duration estimates per operation (seconds)
        durations = {
            "domains": 2,  # Fast - small YAML file
            "symbols": 15 if not force_refresh else 30,  # Full codebase scan
            "vectors_policies": 10,  # ~20-50 policy files
            "vectors_patterns": 5,  # ~10-20 pattern files
            "vectors_symbols": 20 if not force_refresh else 60,  # Large embedding job
        }

        total = sum(durations.get(op, 10) for op in sync_sequence)

        # Add buffer for sequential execution overhead
        if len(sync_sequence) > 1:
            total += len(sync_sequence) * 2

        return total
