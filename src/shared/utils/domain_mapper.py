# src/shared/utils/domain_mapper.py
"""
Constitutional domain mapper - maps module paths to domains defined in Constitution.
This is the SINGLE SOURCE OF TRUTH for domain assignment.
"""

from __future__ import annotations


# ID: dfc9da38-15bb-4723-b673-332eff7a7f43
# ID: b8d370d7-aee8-4326-a313-92f59f6e002e
def map_module_to_domain(module_path: str) -> str:
    """
    Maps a module path to its constitutional domain.

    This mapping MUST match .intent/mind/knowledge/domain_definitions.yaml

    Args:
        module_path: Python module path (e.g., 'features.autonomy.agent')

    Returns:
        Constitutional domain name (e.g., 'autonomy')
    """

    # AUTONOMY: Agent orchestration, decision-making, planning
    if module_path.startswith("features.autonomy."):
        return "autonomy"
    if module_path.startswith("will."):
        return "autonomy"

    # CRATE_PROCESSING: External crate analysis
    if module_path.startswith("features.crate_processing."):
        return "crate_processing"

    # GOVERNANCE: Constitutional enforcement, auditing, policy
    if module_path.startswith("mind."):
        return "governance"
    if module_path.startswith("features.governance."):
        return "governance"

    # INTROSPECTION: Knowledge graph, vectorization, discovery
    if module_path.startswith("features.introspection."):
        return "introspection"

    # MAINTENANCE: Database migrations, cleanup, sync
    if module_path.startswith("features.maintenance."):
        return "maintenance"

    # OPERATIONS: CLI, API, infrastructure, shared
    if module_path.startswith("body."):
        return "operations"
    if module_path.startswith("shared."):
        return "operations"
    if module_path.startswith("api."):
        return "operations"
    if module_path.startswith("features.operations."):
        return "operations"
    if module_path == "main":
        return "operations"

    # PROJECT_LIFECYCLE: Bootstrap, scaffolding
    if module_path.startswith("features.project_lifecycle."):
        return "project_lifecycle"

    # QUALITY: Code quality checks
    if module_path.startswith("features.quality."):
        return "quality"

    # SELF_HEALING: Test generation, auto-remediation
    if module_path.startswith("features.self_healing."):
        return "self_healing"

    # Default: operational infrastructure
    return "operations"
