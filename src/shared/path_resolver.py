# src/shared/path_resolver.py
"""
PathResolver - Single source of truth for all file system paths in CORE.

This module provides a unified interface for accessing file and directory paths
throughout the system, ensuring consistency and eliminating hardcoded path
construction scattered across the codebase.

Constitutional Principle:
    All path access must go through this interface. No direct path construction
    using string concatenation or Path operations outside this module.

NOTE (Dec 2025):
    .intent structure migrated from:
        .intent/charter/{constitution,standards,schemas,...}
    to:
        .intent/{constitution,policies,schemas,standards}

    This resolver supports the new layout as SSOT while providing backward-compatible
    shims (e.g., charter_root) for legacy callers.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 75006a3a-ed9f-4f99-b1dc-8217cb03ad9f
class PathResolver:
    """
    Resolves all file system paths in CORE from constitutional definitions.

    This class provides a typed, validated interface to all paths used by CORE.

    Design Principles:
        - Single source of truth for path resolution
        - Fail fast with clear errors if paths don't exist
        - Type-safe (returns Path objects, not strings)
        - Discoverable (can list available resources)
        - Environment-aware (test vs production paths)
    """

    # ID: 7d2af2b0-8a01-4c3b-bf77-9a6ae1d04c4a
    _DEFAULT_PROMPTS_SUBDIR: ClassVar[tuple[str, ...]] = ("var", "prompts")
    _DEFAULT_CONTEXT_SUBDIR: ClassVar[tuple[str, ...]] = ("var", "context")
    _DEFAULT_MIND_SUBDIR: ClassVar[tuple[str, ...]] = ("var", "mind")

    # Defensive bounds for error messages
    _ERROR_CANDIDATE_LIMIT: ClassVar[int] = 40

    def __init__(self, repo_root: Path, meta: dict[str, Any]):
        """
        Initialize path resolver with repository root and meta configuration.

        Args:
            repo_root: Root directory of the CORE repository
            meta: Parsed contents of .intent/meta.yaml (legacy); may be empty now
        """
        self._repo_root = Path(repo_root)
        self._meta = meta or {}
        self._intent_root = self._repo_root / ".intent"

        # Cache resolved paths for performance
        self._cache: dict[str, Path] = {}

        logger.debug("PathResolver initialized with root: %s", self._repo_root)

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

    # -------------------------------------------------------------------------
    # Backward-compatible shims (legacy callers may still expect these)
    # -------------------------------------------------------------------------

    @property
    # ID: 2b1ae8b0-5f52-4a30-9b02-5b41d92a7e37
    def charter_root(self) -> Path:
        """
        [COMPAT SHIM]
        Legacy code expects .intent/charter/ to exist.

        In the new structure, '.intent/' itself is the charter root equivalent.
        """
        return self._intent_root

    @property
    # ID: 99f013c1-7631-4f98-bb40-ee4a979d371f
    def mind_root(self) -> Path:
        """
        [COMPAT SHIM]
        Legacy code expects .intent/mind/.

        In the new structure, runtime artefacts live under var/.
        Keep 'mind_root' mapped to var/mind to avoid breaking old callers.
        """
        return self._intent_root.joinpath(*self._DEFAULT_MIND_SUBDIR)

    # =========================================================================
    # CONSTITUTION, STANDARDS, POLICIES, SCHEMAS  (New .intent layout SSOT)
    # =========================================================================

    @property
    # ID: a020e1cc-d6ab-4578-a37c-c58e4aa26585
    def constitution_dir(self) -> Path:
        """Directory containing high-level constitutional definitions."""
        return self._intent_root / "constitution"

    @property
    # ID: b90d46b3-39be-4027-8bb4-b747e06a74ca
    def standards_root(self) -> Path:
        """Root of the Standards hierarchy."""
        return self._intent_root / "standards"

    @property
    # ID: 9f0e3d2f-3c18-4c90-8b74-774f9d0643fb
    def policies_root(self) -> Path:
        """Root of executable policies (IntentGuard enforcement rules)."""
        return self._intent_root / "policies"

    @property
    # ID: dd6f3759-9f4b-47fc-9e12-bc0e47544cf3
    def policies_dir(self) -> Path:
        """
        Directory containing policy files.

        IMPORTANT: this now points to `.intent/policies/` (not standards).
        """
        return self.policies_root

    @property
    # ID: e702b3b8-cf9b-4d3f-be08-a89eac144acf
    def schemas_dir(self) -> Path:
        """Directory containing JSON schemas."""
        return self._intent_root / "schemas"

    # -------------------------------------------------------------------------
    # Standards & Policies lookup helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _normalize_intent_key(key: str) -> str:
        """
        Normalize an intent key.

        - Strips leading separators
        - Removes trailing .json/.yaml if present
        - Converts Windows separators to '/'
        """
        k = (key or "").strip()
        k = k.lstrip("/").lstrip("\\")
        k = k.replace("\\", "/")
        if k.endswith(".json"):
            k = k[:-5]
        elif k.endswith(".yaml"):
            k = k[:-5]
        return k

    @staticmethod
    def _relative_key(root: Path, file_path: Path) -> str:
        """Return a canonical key for file_path relative to root (without extension)."""
        rel = file_path.relative_to(root)
        # Drop extension
        rel_no_ext = rel.with_suffix("")
        return rel_no_ext.as_posix()

    def _candidates_message(self, keys: list[str]) -> str:
        """Format candidates for errors with a hard cap."""
        if not keys:
            return ""
        keys_sorted = sorted(keys)
        if len(keys_sorted) <= self._ERROR_CANDIDATE_LIMIT:
            return ", ".join(keys_sorted)
        shown = keys_sorted[: self._ERROR_CANDIDATE_LIMIT]
        return f"{', '.join(shown)} ... (+{len(keys_sorted) - len(shown)} more)"

    # ID: 27d157c2-2eb5-4a09-9904-c60f86af1bfc
    def policy(self, name: str) -> Path:
        """
        Get path to a specific executable policy file under `.intent/policies/`.

        Canonical usage (preferred):
            policy("code/code_standards")  -> .intent/policies/code/code_standards.json

        Backward compatible usage:
            policy("code_standards")       -> searches recursively under policies/
                                             (fails if ambiguous)

        Tries .json first, falls back to .yaml.
        """
        key = self._normalize_intent_key(name)
        if not key:
            raise ValueError("policy(name) requires a non-empty policy key")

        # Fast path cache
        cache_key = f"policy::{key}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        # 1) Deterministic resolution: treat key as a relative path under policies/
        json_path = self.policies_dir / f"{key}.json"
        if json_path.exists():
            self._cache[cache_key] = json_path
            return json_path

        yaml_path = self.policies_dir / f"{key}.yaml"
        if yaml_path.exists():
            self._cache[cache_key] = yaml_path
            return yaml_path

        # 2) Backward compatible fallback: if no hierarchy specified, try recursive match.
        #    This is intentionally strict: ambiguity is an error.
        if "/" not in key:
            json_matches = list(self.policies_dir.rglob(f"{key}.json"))
            yaml_matches = list(self.policies_dir.rglob(f"{key}.yaml"))
            matches = json_matches or yaml_matches

            if len(matches) == 1:
                resolved = matches[0]
                self._cache[cache_key] = resolved
                return resolved

            if len(matches) > 1:
                candidate_keys = [
                    self._relative_key(self.policies_dir, p) for p in matches
                ]
                raise FileNotFoundError(
                    "Policy key is ambiguous. "
                    f"Requested '{name}' matched multiple policies under {self.policies_dir}. "
                    "Use a canonical policy key (e.g. 'code/code_standards'). "
                    f"Candidates: {self._candidates_message(candidate_keys)}"
                )

        # 3) Not found: show canonical list (keys, not stems)
        available = self.list_policies()
        raise FileNotFoundError(
            f"Policy '{name}' not found in {self.policies_dir}. "
            "Use canonical keys relative to .intent/policies (e.g. 'code/code_standards'). "
            f"Available policies: {self._candidates_message(available)}"
        )

    # ID: 86299442-b2ae-45e1-8de0-c87345d8951b
    def list_policies(self) -> list[str]:
        """
        List all available executable policies (from `.intent/policies/`).

        Returns canonical keys (relative paths under policies root), e.g.:
            - architecture/agent_governance
            - code/code_standards
            - operations/safety
        """
        if not self.policies_dir.exists():
            return []

        keys: set[str] = set()
        for p in self.policies_dir.rglob("*.json"):
            keys.add(self._relative_key(self.policies_dir, p))
        for p in self.policies_dir.rglob("*.yaml"):
            keys.add(self._relative_key(self.policies_dir, p))

        return sorted(keys)

    # -------------------------------------------------------------------------
    # Patterns (kept as-is; map to standards/architecture as before)
    # -------------------------------------------------------------------------

    @property
    # ID: e5a7ba49-2e77-42cb-8496-f95a0da63a10
    def patterns_dir(self) -> Path:
        """
        Directory containing patterns.

        Kept aligned with prior design: patterns live under architecture standards.
        """
        return self.standards_root / "architecture"

    # ID: db237a05-9649-4882-b982-37d989b3a4ba
    def pattern(self, name: str) -> Path:
        """
        Get path to a specific pattern file (json preferred, yaml fallback).

        Canonical usage:
            pattern("some_pattern") or pattern("subdir/some_pattern") if you ever add nesting.
        """
        key = self._normalize_intent_key(name)
        if not key:
            raise ValueError("pattern(name) requires a non-empty pattern key")

        cache_key = f"pattern::{key}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        json_path = self.patterns_dir / f"{key}.json"
        if json_path.exists():
            self._cache[cache_key] = json_path
            return json_path

        yaml_path = self.patterns_dir / f"{key}.yaml"
        if yaml_path.exists():
            self._cache[cache_key] = yaml_path
            return yaml_path

        if "/" not in key:
            json_matches = list(self.patterns_dir.rglob(f"{key}.json"))
            yaml_matches = list(self.patterns_dir.rglob(f"{key}.yaml"))
            matches = json_matches or yaml_matches

            if len(matches) == 1:
                resolved = matches[0]
                self._cache[cache_key] = resolved
                return resolved

            if len(matches) > 1:
                candidate_keys = [
                    self._relative_key(self.patterns_dir, p) for p in matches
                ]
                raise FileNotFoundError(
                    "Pattern key is ambiguous. "
                    f"Requested '{name}' matched multiple patterns under {self.patterns_dir}. "
                    f"Candidates: {self._candidates_message(candidate_keys)}"
                )

        raise FileNotFoundError(f"Pattern '{name}' not found in {self.patterns_dir}")

    # ID: 631ade1f-a080-4f33-852e-d8b5ef9888bd
    def list_patterns(self) -> list[str]:
        """List all available patterns (architecture standards) as canonical keys."""
        if not self.patterns_dir.exists():
            return []

        keys: set[str] = set()
        for p in self.patterns_dir.rglob("*.json"):
            keys.add(self._relative_key(self.patterns_dir, p))
        for p in self.patterns_dir.rglob("*.yaml"):
            keys.add(self._relative_key(self.patterns_dir, p))

        return sorted(keys)

    # =========================================================================
    # PROPOSALS
    # =========================================================================

    @property
    # ID: f1e0459b-ae68-4788-af26-9fbef74f719a
    def proposals_dir(self) -> Path:
        """Directory containing constitutional change proposals (work/proposals)."""
        proposals = self.work_dir / "proposals"
        proposals.mkdir(parents=True, exist_ok=True)
        return proposals

    # ID: 741fdbef-133b-4f84-961f-310311c67cc5
    def proposal(self, proposal_id: str) -> Path:
        """Get path to a specific proposal file."""
        return self.proposals_dir / f"{proposal_id}.yaml"

    # =========================================================================
    # PROMPTS (you confirmed they are in var/)
    # =========================================================================

    @property
    # ID: d0ba9710-94d2-4ad5-9b96-47f84c98b644
    def prompts_dir(self) -> Path:
        """Directory containing LLM prompt templates (runtime artefacts)."""
        return self._repo_root.joinpath(*self._DEFAULT_PROMPTS_SUBDIR)

    # ID: d3463541-f011-4eb0-bc98-799962936786
    def prompt(self, name: str) -> Path:
        """Get path to a specific prompt template (.prompt)."""
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
        """List all available prompt templates."""
        if not self.prompts_dir.exists():
            return []
        return [p.stem for p in self.prompts_dir.glob("*.prompt")]

    # =========================================================================
    # CONTEXT SCHEMA (manage.define-symbols expects this area)
    # =========================================================================

    @property
    # ID: 5e8d4b18-11df-4fe8-b1b0-74d4c2d6f44a
    def context_dir(self) -> Path:
        """Directory containing runtime context definitions."""
        return self._repo_root.joinpath("var", "context")

    # ID: 4a5a5d3e-8d54-4f07-9a31-08d2a2bb2f60
    def context_schema_path(self) -> Path:
        """Path to runtime context schema file."""
        return self.context_dir / "schema.yaml"

    # =========================================================================
    # MIND EXPORTS (kept)
    # =========================================================================

    @property
    # ID: 243ebce3-db6e-407e-9f53-7fd4669728b9
    def mind_export_dir(self) -> Path:
        """Directory for Mind state exports."""
        return self._repo_root / "var" / "core" / "mind_export" / "mind_export"

    # ID: e631bf4f-5e70-491c-a685-fa87754af9cf
    def mind_export(self, resource: str) -> Path:
        """Get path to a Mind export file."""
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
        errors: list[str] = []

        required_dirs = [
            (self.intent_root, ".intent/"),
            (self.constitution_dir, ".intent/constitution/"),
            (self.standards_root, ".intent/standards/"),
            (self.policies_dir, ".intent/policies/"),
            (self.schemas_dir, ".intent/schemas/"),
            (self.proposals_dir, "work/proposals/"),
            (self.prompts_dir, "var/prompts/"),
            (self.context_dir, "var/context/"),
        ]

        for path, name in required_dirs:
            if not path.exists():
                errors.append(f"Missing required directory: {name} at {path}")

        return errors

    def __repr__(self) -> str:
        return f"PathResolver(root={self._repo_root})"
