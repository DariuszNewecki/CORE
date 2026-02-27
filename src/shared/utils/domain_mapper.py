# src/shared/utils/domain_mapper.py
"""
Constitutional domain mapper - maps module paths to domains defined in Constitution.
This is the SINGLE SOURCE OF TRUTH for domain assignment.

UPDATE (Wave 1 Reorganization):
Supports both legacy 'features.X' and new layered 'body/will/mind.X' paths.
"""

from __future__ import annotations


# src/shared/utils/domain_mapper.py


# ID: a8fe04f1-60ec-4418-8727-2eaf690d1543
def map_module_to_domain(module_path: str) -> str:
    """
    Maps a module path to its constitutional domain.
    REFACTORED: Removed legacy 'features' prefixes.
    """

    # AUTONOMY: Agent orchestration, decision-making, planning
    if module_path.startswith("will.autonomy."):
        return "autonomy"
    if module_path.startswith("will."):  # Primary catch-all for Agent logic
        return "autonomy"

    # CRATE_PROCESSING: External crate analysis
    if module_path.startswith("body.crate_processing."):
        return "crate_processing"

    # GOVERNANCE: Constitutional enforcement, auditing, policy
    if module_path.startswith(("mind.governance.", "mind.logic.engines.")):
        return "governance"

    # INTROSPECTION: Knowledge graph, vectorization, discovery
    if module_path.startswith("body.introspection."):
        return "introspection"

    # MAINTENANCE: Database migrations, cleanup, sync
    if module_path.startswith("body.maintenance."):
        return "maintenance"

    # OPERATIONS: CLI, API, infrastructure, shared
    if module_path.startswith(("body.cli.", "body.operations.", "shared.", "api.")):
        return "operations"

    # PROJECT_LIFECYCLE: Bootstrap, scaffolding
    if module_path.startswith("body.project_lifecycle."):
        return "project_lifecycle"

    # QUALITY: Code quality checks
    if module_path.startswith("body.quality."):
        return "quality"

    # SELF_HEALING: Test generation, auto-remediation
    if module_path.startswith(("body.self_healing.", "will.self_healing.")):
        return "self_healing"

    return "operations"
