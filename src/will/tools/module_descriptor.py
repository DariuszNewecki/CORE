# src/will/tools/module_descriptor.py
"""
Module Description Generator

Generates rich, distinctive descriptions for modules based on their
path, name, layer, and contents. These descriptions become the semantic
anchors that enable accurate placement decisions.

Constitutional Alignment:
- clarity_first: Explicit, distinctive module purposes
"""

from __future__ import annotations


# ID: 993434f0-20b9-423d-8204-a697627ff3f9
class ModuleDescriptor:
    """Generates rich, semantic descriptions for modules."""

    @staticmethod
    # ID: a65ef200-b518-4926-855a-bab9a4e4997e
    def generate(
        module_path: str,
        module_name: str,
        layer: str,
        files: list[str],
    ) -> str:
        """
        Generate rich, distinctive module description.

        Order matters: Check SPECIFIC patterns before GENERIC ones!

        Args:
            module_path: Full module path (e.g., "domain/validators")
            module_name: Module directory name
            layer: Architectural layer
            files: List of Python files in module

        Returns:
            Rich description for semantic embedding
        """
        path_lower = module_path.lower()

        # SPECIFIC PATTERNS FIRST (to prevent generic catch-all matching)

        # Test-related (VERY SPECIFIC - check before generic "generation")
        if "test" in path_lower:
            return (
                f"Automated pytest test case generation for {module_name}. "
                f"Creates unit tests, handles test repair, manages test execution. "
                f"For testing infrastructure only, not general code generation."
            )

        # Validators (SPECIFIC domain pattern)
        if "validator" in path_lower:
            return (
                f"Domain validation logic for {module_name}. "
                f"Validates business rules and data integrity constraints. "
                f"Returns ValidationResult with success/failure and error details."
            )

        # Utils/Helpers (SPECIFIC - pure utilities)
        if "utils" in path_lower or "helper" in path_lower:
            return ModuleDescriptor._describe_utils(files)

        # Introspection/Analysis (SPECIFIC system analysis)
        if (
            "introspect" in path_lower
            or "analysis" in path_lower
            or "discover" in path_lower
        ):
            return (
                f"System introspection and codebase analysis for {module_name}. "
                f"Discovers code structure, analyzes dependencies, extracts metadata. "
                f"For understanding existing code, not generating new code."
            )

        # GENERIC PATTERNS LAST (broader matching)

        # Formatting/Generation (GENERIC - after specific types)
        if "format" in path_lower or "generat" in path_lower:
            return (
                f"General code formatting and generation for {module_name}. "
                f"Transforms or generates production code programmatically. "
                f"Not for tests - for actual feature code."
            )

        # Domain models
        if "model" in path_lower and layer == "domain":
            return (
                f"Domain models for {module_name}. "
                f"Core business entities and value objects with domain logic."
            )

        # Services (layer-specific)
        if layer == "services":
            return (
                f"Infrastructure service for {module_name}. "
                f"Manages external system integration, connections, and lifecycle."
            )

        # Agents
        if "agent" in path_lower:
            return (
                f"Autonomous agent for {module_name}. "
                f"AI-powered decision making and task execution."
            )

        # Actions/Handlers
        if "action" in path_lower or "handler" in path_lower:
            return (
                f"Action handlers for {module_name}. "
                f"Executes autonomous operations with constitutional governance."
            )

        # CLI
        if "cli" in path_lower or "command" in path_lower:
            return (
                f"Command-line interface for {module_name}. "
                f"User-facing commands and interaction logic."
            )

        # Default: infer from module name
        return (
            f"Handles {module_name.replace('_', ' ')} operations in the {layer} layer."
        )

    @staticmethod
    def _describe_utils(files: list[str]) -> str:
        """Generate description for utility modules based on files."""
        file_themes = []

        if any("path" in f.lower() for f in files):
            file_themes.append("file path operations")
        if any("json" in f.lower() or "yaml" in f.lower() for f in files):
            file_themes.append("data format parsing")
        if any("text" in f.lower() or "string" in f.lower() for f in files):
            file_themes.append("text processing")
        if any("time" in f.lower() or "date" in f.lower() for f in files):
            file_themes.append("date/time utilities")

        if file_themes:
            themes = ", ".join(file_themes)
            return (
                f"Pure utility functions for {themes}. "
                f"Stateless helpers with no business logic or external dependencies. "
                f"Reusable across all layers."
            )
        else:
            return (
                "Generic utility functions and helpers. "
                "Pure, stateless functions with no side effects. "
                "Simple operations like string manipulation, data conversion."
            )
