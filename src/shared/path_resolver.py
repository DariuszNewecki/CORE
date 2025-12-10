# src/shared/path_resolver.py
"""
PathResolver - Single source of truth for all file system paths in CORE.

This module provides a unified interface for accessing file and directory paths
throughout the system, ensuring consistency and eliminating hardcoded path
construction scattered across the codebase.

Constitutional Principle:
    All path access must go through this interface. No direct path construction
    using string concatenation or Path operations outside this module.

Usage:
    from shared.config import settings

    # Access paths through the interface
    proposal_dir = settings.paths.proposals_dir
    prompt = settings.paths.prompt("refactor_outlier")
    policy = settings.paths.policy("safety_framework")
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 75006a3a-ed9f-4f99-b1dc-8217cb03ad9f
class PathResolver:
    """
    Resolves all file system paths in CORE from constitutional definitions.

    This class provides a typed, validated interface to all paths used by CORE,
    grounded in .intent/meta.yaml and constitutional structure.

    Design Principles:
        - Single source of truth for path resolution
        - Fail fast with clear errors if paths don't exist
        - Type-safe (returns Path objects, not strings)
        - Discoverable (can list available resources)
        - Environment-aware (test vs production paths)
    """

    def __init__(self, repo_root: Path, meta: dict[str, Any]):
        """
        Initialize path resolver with repository root and meta configuration.

        Args:
            repo_root: Root directory of the CORE repository
            meta: Parsed contents of .intent/meta.yaml
        """
        self._repo_root = repo_root
        self._meta = meta
        self._intent_root = repo_root / ".intent"

        # Cache resolved paths for performance
        self._cache: dict[str, Path] = {}

        logger.debug("PathResolver initialized with root: %s", repo_root)

    # =========================================================================
    # CORE DIRECTORIES
    # =========================================================================

    @property
    # ID: d6a0e84b-8969-40ac-9161-01be26f825f5
    def repo_root(self) -> Path:
        """Root directory of the CORE repository."""
        return self._repo_root

    @property
    # ID: f77058bf-c12b-44d6-9020-36e436af3473
    def intent_root(self) -> Path:
        """Root of .intent/ directory (constitutional definitions)."""
        return self._intent_root

    @property
    # ID: f7e26b82-5235-4996-b9ef-c63368a1ac26
    def charter_root(self) -> Path:
        """Root of .intent/charter/ (constitution, policies, patterns)."""
        return self._intent_root / "charter"

    @property
    # ID: 99f013c1-7631-4f98-bb40-ee4a979d371f
    def mind_root(self) -> Path:
        """Root of .intent/mind/ (knowledge, config, IR)."""
        return self._intent_root / "mind"

    # =========================================================================
    # PROPOSALS
    # =========================================================================

    @property
    # ID: f1e0459b-ae68-4788-af26-9fbef74f719a
    def proposals_dir(self) -> Path:
        """Directory containing constitutional change proposals."""
        return self._intent_root / "proposals"

    # ID: 741fdbef-133b-4f84-961f-310311c67cc5
    def proposal(self, proposal_id: str) -> Path:
        """
        Get path to a specific proposal file.

        Args:
            proposal_id: Proposal identifier (e.g., "cr-2024-001")

        Returns:
            Path to proposal YAML file
        """
        return self.proposals_dir / f"{proposal_id}.yaml"

    # =========================================================================
    # PROMPTS
    # =========================================================================

    @property
    # ID: d0ba9710-94d2-4ad5-9b96-47f84c98b644
    def prompts_dir(self) -> Path:
        """Directory containing LLM prompt templates."""
        prompts_rel = self._meta.get("mind", {}).get("prompts_dir", "mind/prompts")
        return self._intent_root / prompts_rel

    # ID: d3463541-f011-4eb0-bc98-799962936786
    def prompt(self, name: str) -> Path:
        """
        Get path to a specific prompt template.

        Args:
            name: Prompt name (without .prompt extension)

        Returns:
            Path to prompt file

        Raises:
            FileNotFoundError: If prompt doesn't exist
        """
        prompt_path = self.prompts_dir / f"{name}.prompt"

        if not prompt_path.exists():
            available = self.list_prompts()
            raise FileNotFoundError(
                f"Prompt '{name}' not found at {prompt_path}. "
                f"Available prompts: {', '.join(available)}"
            )

        return prompt_path

    # ID: ca8f8d94-eb47-4163-af8e-8baff04e716c
    def list_prompts(self) -> list[str]:
        """
        List all available prompt templates.

        Returns:
            List of prompt names (without .prompt extension)
        """
        if not self.prompts_dir.exists():
            return []

        return [p.stem for p in self.prompts_dir.glob("*.prompt")]

    # =========================================================================
    # POLICIES
    # =========================================================================

    @property
    # ID: dd6f3759-9f4b-47fc-9e12-bc0e47544cf3
    def policies_dir(self) -> Path:
        """Directory containing constitutional policies."""
        return self.charter_root / "policies"

    # ID: 27d157c2-2eb5-4a09-9904-c60f86af1bfc
    def policy(self, name: str) -> Path:
        """
        Get path to a specific policy file.

        Args:
            name: Policy name (without .yaml extension)

        Returns:
            Path to policy YAML file

        Raises:
            FileNotFoundError: If policy doesn't exist
        """
        policy_path = self.policies_dir / f"{name}.yaml"

        if not policy_path.exists():
            available = self.list_policies()
            raise FileNotFoundError(
                f"Policy '{name}' not found at {policy_path}. "
                f"Available policies: {', '.join(available)}"
            )

        return policy_path

    # ID: 86299442-b2ae-45e1-8de0-c87345d8951b
    def list_policies(self) -> list[str]:
        """
        List all available policies.

        Returns:
            List of policy names (without .yaml extension)
        """
        if not self.policies_dir.exists():
            return []

        return [p.stem for p in self.policies_dir.glob("*.yaml")]

    # =========================================================================
    # PATTERNS
    # =========================================================================

    @property
    # ID: e5a7ba49-2e77-42cb-8496-f95a0da63a10
    def patterns_dir(self) -> Path:
        """Directory containing architectural patterns."""
        return self.charter_root / "patterns"

    # ID: db237a05-9649-4882-b982-37d989b3a4ba
    def pattern(self, name: str) -> Path:
        """
        Get path to a specific pattern file.

        Args:
            name: Pattern name (without .yaml extension)

        Returns:
            Path to pattern YAML file
        """
        return self.patterns_dir / f"{name}.yaml"

    # ID: 631ade1f-a080-4f33-852e-d8b5ef9888bd
    def list_patterns(self) -> list[str]:
        """List all available patterns."""
        if not self.patterns_dir.exists():
            return []

        return [p.stem for p in self.patterns_dir.glob("*.yaml")]

    # =========================================================================
    # SCHEMAS
    # =========================================================================

    @property
    # ID: e702b3b8-cf9b-4d3f-be08-a89eac144acf
    def schemas_dir(self) -> Path:
        """Directory containing JSON schemas."""
        return self.charter_root / "schemas"

    # ID: e3575151-7c9f-4dbf-83d6-51764a2cb2ac
    def schema(self, category: str, name: str) -> Path:
        """
        Get path to a specific schema file.

        Args:
            category: Schema category (e.g., "core", "governance", "operations")
            name: Schema name (without .json extension)

        Returns:
            Path to schema JSON file
        """
        return self.schemas_dir / category / f"{name}.json"

    # =========================================================================
    # MIND EXPORTS
    # =========================================================================

    @property
    # ID: 243ebce3-db6e-407e-9f53-7fd4669728b9
    def mind_export_dir(self) -> Path:
        """Directory for Mind state exports."""
        return self._intent_root / "mind_export"

    # ID: e631bf4f-5e70-491c-a685-fa87754af9cf
    def mind_export(self, resource: str) -> Path:
        """
        Get path to a Mind export file.

        Args:
            resource: Resource name (e.g., "cognitive_roles", "capabilities")

        Returns:
            Path to export YAML file
        """
        return self.mind_export_dir / f"{resource}.yaml"

    # =========================================================================
    # WORK DIRECTORIES
    # =========================================================================

    @property
    # ID: 78d4598f-1267-4607-b3fb-469f4f092a90
    def work_dir(self) -> Path:
        """Temporary work directory (not in git)."""
        work = self._repo_root / "work"
        work.mkdir(exist_ok=True)
        return work

    @property
    # ID: 92dfe18e-0883-4434-b90a-a0ebbc8bc957
    def reports_dir(self) -> Path:
        """Directory for generated reports."""
        reports = self._repo_root / "reports"
        reports.mkdir(exist_ok=True)
        return reports

    @property
    # ID: 2b6c07b8-b2bf-4d34-99db-94652747645b
    def logs_dir(self) -> Path:
        """Directory for log files."""
        logs = self._repo_root / "logs"
        logs.mkdir(exist_ok=True)
        return logs

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    # ID: 2374f137-6c7f-4ecc-a804-d3e8d18dd137
    def validate_structure(self) -> list[str]:
        """
        Validate that all expected directories exist.

        Returns:
            List of validation errors (empty if all valid)
        """
        errors = []

        required_dirs = [
            (self.intent_root, ".intent/"),
            (self.charter_root, ".intent/charter/"),
            (self.mind_root, ".intent/mind/"),
            (self.proposals_dir, ".intent/proposals/"),
            (self.prompts_dir, "prompts directory"),
            (self.policies_dir, "policies directory"),
            (self.patterns_dir, "patterns directory"),
        ]

        for path, name in required_dirs:
            if not path.exists():
                errors.append(f"Missing required directory: {name} at {path}")

        return errors

    def __repr__(self) -> str:
        return f"PathResolver(root={self._repo_root})"
