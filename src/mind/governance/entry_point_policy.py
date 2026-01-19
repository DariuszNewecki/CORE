# src/mind/governance/entry_point_policy.py

"""
Entry point allow-list policy for audit severity downgrading.
"""

from __future__ import annotations

from collections.abc import Iterable


# ID: 86699225-ae44-4a9a-926c-87bb365f5b7c
class EntryPointAllowList:
    """
    Allow-list of entry_point_type values for which we downgrade dead-public-symbol findings.

    These are architectural patterns that intentionally have public symbols
    without direct internal callers (CLI commands, base classes, data models, etc).
    """

    def __init__(self, allowed_types: Iterable[str]) -> None:
        self.allowed = {t.strip() for t in allowed_types if t and t.strip()}

    @classmethod
    # ID: a0594887-ebb4-429f-b2cf-976e266e2796
    def default(cls) -> EntryPointAllowList:
        """Standard allow-list based on CORE's architectural patterns."""
        return cls(
            allowed_types=[
                # Structural/data constructs
                "data_model",
                "enum",
                "magic_method",
                "visitor_method",
                "base_class",
                "boilerplate_method",
                # CLI & wrappers
                "cli_command",
                "cli_wrapper",
                "registry_accessor",
                # Orchestration/factories
                "orchestrator",
                "factory",
                # Providers/adapters/clients
                "provider_method",
                "client_surface",
                "client_adapter",
                "io_handler",
                "git_adapter",
                "utility_function",
                # Knowledge & governance pipelines
                "knowledge_core",
                "governance_check",
                "auditor_pipeline",
                # Capabilities
                "capability",
            ]
        )

    def __contains__(self, entry_point_type: str | None) -> bool:
        """Check if an entry_point_type is in the allow-list."""
        return bool(entry_point_type) and entry_point_type in self.allowed
