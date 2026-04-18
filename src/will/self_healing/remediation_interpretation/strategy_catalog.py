# src/will/self_healing/remediation_interpretation/strategy_catalog.py

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
# ID: 9e57585d-e58b-4f28-9bc3-299314245fc4
class StrategyTemplate:
    """
    Deterministic remediation strategy template.

    This is not yet a selected strategy for a specific file. It is a catalog
    entry that can be evaluated against a file role, responsibility clusters,
    and violation patterns.
    """

    strategy_id: str
    summary: str
    rationale: str
    risk_level: str
    preserves_contract: bool
    preferred_for_roles: tuple[str, ...] = ()
    preferred_for_rules: tuple[str, ...] = ()
    discouraged_for_roles: tuple[str, ...] = ()
    discouraged_for_rules: tuple[str, ...] = ()


# ID: aed7d1af-2f94-4f0f-9a16-0df0f4d66f7f
class StrategyCatalog:
    """
    Deterministic catalog of remediation strategies.

    The catalog provides the bounded strategy vocabulary that the selector may
    rank for a given violation context. This prevents freeform or opportunistic
    planning and keeps remediation interpretation explainable and governed.

    Design:
    - static, deterministic strategy inventory
    - no LLM
    - no I/O
    - no repo traversal
    """

    # ID: 5b847e91-d0e6-4bd4-8db3-f9cb6dcae6d2
    def list_templates(self) -> list[StrategyTemplate]:
        """Return all available remediation strategy templates."""
        return [
            StrategyTemplate(
                strategy_id="extract_helper_functions",
                summary="Extract cohesive helper functions from a large file without changing ownership boundaries.",
                rationale=(
                    "Useful when the file is oversized or operationally dense, "
                    "but its primary responsibility should remain in place."
                ),
                risk_level="low",
                preserves_contract=True,
                preferred_for_roles=(
                    "worker.sensor",
                    "worker.actor",
                    "service",
                    "route",
                    "utility",
                ),
                preferred_for_rules=(
                    "architecture.max_file_size",
                    "modularity",
                ),
            ),
            StrategyTemplate(
                strategy_id="extract_private_methods",
                summary="Split large methods or orchestration blocks into private methods within the same class.",
                rationale=(
                    "Useful when the main class is valid but individual methods or "
                    "procedural blocks are too large or mixed."
                ),
                risk_level="low",
                preserves_contract=True,
                preferred_for_roles=(
                    "worker.sensor",
                    "worker.actor",
                    "service",
                    "repository",
                ),
                preferred_for_rules=(
                    "architecture.max_file_size",
                    "modularity",
                ),
            ),
            StrategyTemplate(
                strategy_id="extract_service_collaborator",
                summary="Move a distinct operational concern into a dedicated collaborator service.",
                rationale=(
                    "Useful when the file contains a stable sub-responsibility that "
                    "deserves its own orchestration or processing surface."
                ),
                risk_level="medium",
                preserves_contract=True,
                preferred_for_roles=(
                    "worker.actor",
                    "service",
                    "route",
                ),
                preferred_for_rules=(
                    "architecture.max_file_size",
                    "modularity",
                    "coupling",
                ),
                discouraged_for_roles=(
                    "model",
                    "repository",
                ),
            ),
            StrategyTemplate(
                strategy_id="extract_analysis_service",
                summary="Move deterministic analysis or interpretation logic into a dedicated service.",
                rationale=(
                    "Useful when a worker or route is mixing coordination with "
                    "analysis/planning logic."
                ),
                risk_level="medium",
                preserves_contract=True,
                preferred_for_roles=(
                    "worker.sensor",
                    "worker.actor",
                    "route",
                ),
                preferred_for_rules=(
                    "architecture.max_file_size",
                    "modularity",
                    "separation",
                ),
            ),
            StrategyTemplate(
                strategy_id="extract_repository_access",
                summary="Move data access behavior into a repository boundary.",
                rationale=(
                    "Useful when business logic and persistence concerns are mixed "
                    "in the same module."
                ),
                risk_level="medium",
                preserves_contract=True,
                preferred_for_roles=(
                    "service",
                    "worker.actor",
                    "route",
                ),
                preferred_for_rules=(
                    "coupling",
                    "boundary",
                    "separation",
                ),
                discouraged_for_roles=(
                    "repository",
                    "model",
                ),
            ),
            StrategyTemplate(
                strategy_id="split_module_by_responsibility",
                summary="Split the module into multiple files along clear responsibility boundaries.",
                rationale=(
                    "Useful when multiple top-level concerns are co-located and local "
                    "function extraction is not enough."
                ),
                risk_level="medium",
                preserves_contract=True,
                preferred_for_roles=(
                    "service",
                    "worker.actor",
                    "worker.sensor",
                    "utility",
                ),
                preferred_for_rules=(
                    "architecture.max_file_size",
                    "modularity",
                    "coupling",
                ),
            ),
            StrategyTemplate(
                strategy_id="reduce_import_surface",
                summary="Simplify dependency surface by reducing direct imports and isolating collaborations.",
                rationale=(
                    "Useful when the module depends on too many collaborators and "
                    "structural complexity is driven by broad import spread."
                ),
                risk_level="medium",
                preserves_contract=True,
                preferred_for_roles=(
                    "service",
                    "worker.actor",
                    "worker.sensor",
                    "route",
                ),
                preferred_for_rules=(
                    "coupling",
                    "boundary",
                    "modularity",
                ),
            ),
            StrategyTemplate(
                strategy_id="preserve_role_extract_helpers_only",
                summary="Keep the file in its current architectural role and apply only minimal helper extraction.",
                rationale=(
                    "Useful when role integrity is more important than aggressive "
                    "restructuring, especially for constitutionally sensitive files."
                ),
                risk_level="low",
                preserves_contract=True,
                preferred_for_roles=(
                    "worker.sensor",
                    "worker.actor",
                    "repository",
                    "model",
                    "cli",
                ),
                preferred_for_rules=(
                    "architecture.max_file_size",
                    "modularity",
                ),
            ),
            StrategyTemplate(
                strategy_id="defer_structural_split_choose_local_cleanup",
                summary="Prefer local cleanup over file splitting because the current evidence for a larger split is weak.",
                rationale=(
                    "Useful as a conservative fallback when the file is large but "
                    "responsibility clusters are not yet cleanly separable."
                ),
                risk_level="low",
                preserves_contract=True,
                preferred_for_roles=(
                    "worker",
                    "worker.sensor",
                    "worker.actor",
                    "service",
                    "utility",
                    "unknown",
                ),
                preferred_for_rules=(
                    "architecture.max_file_size",
                    "modularity",
                ),
            ),
        ]

    # ID: b6ce4269-b4c2-48be-bd5b-2ea2bc56f2dc
    def get_template(self, strategy_id: str) -> StrategyTemplate | None:
        """Return one strategy template by ID."""
        for template in self.list_templates():
            if template.strategy_id == strategy_id:
                return template
        return None
