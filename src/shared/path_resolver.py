# src/shared/path_resolver.py
"""
PathResolver - Single source of truth for all repository-relative paths in CORE.

Key boundary rules:
- PathResolver RESOLVES paths only. It must not mutate the filesystem (mkdir, write, copy, delete).
- Filesystem mutations (including mkdir) belong to FileHandler (or other explicitly governed mutation surfaces).
- PathResolver may return paths under `.intent/` for READ/LOOKUP purposes, but should not read or write files.

Design:
- Deterministic path construction.
- No side effects.
- Minimal, explicit public surface: resolve directories and files used across CORE.
"""

from __future__ import annotations

import glob
from pathlib import Path
from typing import Any, ClassVar

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 75006a3a-ed9f-4f99-b1dc-8217cb03ad9f
class PathResolver:
    """
    Resolves all repository-relative paths in CORE.

    Important:
        This class is NOT a filesystem manager. It must not create directories.
        Use FileHandler for mkdir/copy/write operations.

    Notes on `.intent/`:
        - Returning a Path under `.intent/` is allowed (resolution).
        - Reading/writing `.intent/` should be mediated by IntentRepository / governed services.
    """

    # Runtime structure defaults (relative to repo root)
    _DEFAULT_PROMPTS_SUBDIR: ClassVar[tuple[str, ...]] = ("var", "prompts")
    _DEFAULT_CONTEXT_SUBDIR: ClassVar[tuple[str, ...]] = ("var", "context")
    _DEFAULT_CONTEXT_CACHE_SUBDIR: ClassVar[tuple[str, ...]] = (
        "var",
        "cache",
        "context",
    )
    _DEFAULT_KNOWLEDGE_SUBDIR: ClassVar[tuple[str, ...]] = ("var", "mind", "knowledge")
    _DEFAULT_EXPORTS_SUBDIR: ClassVar[tuple[str, ...]] = ("var", "exports")
    _DEFAULT_LOGS_SUBDIR: ClassVar[tuple[str, ...]] = ("var", "logs")
    _DEFAULT_REPORTS_SUBDIR: ClassVar[tuple[str, ...]] = ("var", "reports")
    _DEFAULT_WORKFLOWS_SUBDIR: ClassVar[tuple[str, ...]] = ("var", "workflows")
    _DEFAULT_BUILD_SUBDIR: ClassVar[tuple[str, ...]] = ("var", "build")

    @classmethod
    # ID: b4295e1a-8a41-4f2f-9383-d18990179ba9
    def from_repo(
        cls,
        repo_root: Path,
        intent_root: Path | None = None,
        meta: dict[str, Any] | None = None,
    ) -> PathResolver:
        """
        Convenience constructor used by Settings/config.

        This method MUST remain side-effect free (no mkdir/write).
        It simply wires repo_root + optional intent_root override.

        Args:
            repo_root: Root directory of the CORE repository.
            intent_root: Optional override for `.intent/` root (defaults to repo_root / ".intent").
            meta: Optional parsed contents of .intent/meta.yaml (legacy). May be empty/None.
        """
        resolver = cls(repo_root=repo_root, meta=meta)
        if intent_root is not None:
            resolver._intent_root = Path(intent_root)
        return resolver

    def __init__(self, repo_root: Path, meta: dict[str, Any] | None = None):
        """
        Args:
            repo_root: Root directory of the CORE repository.
            meta: Parsed contents of .intent/meta.yaml (legacy). May be empty/None.
        """
        self._repo_root = Path(repo_root)
        self._meta: dict[str, Any] = meta or {}
        self._intent_root = self._repo_root / ".intent"

        logger.debug("PathResolver initialized (repo_root=%s)", self._repo_root)

    # =========================================================================
    # CORE ROOTS
    # =========================================================================

    @property
    # ID: d6a0e84b-8969-40ac-9161-01be26f825f5
    def repo_root(self) -> Path:
        """Repository root path."""
        return self._repo_root

    @property
    # ID: f77058bf-c12b-44d6-9020-36e436af3473
    def intent_root(self) -> Path:
        """Root of .intent/ (path only; do not mutate)."""
        return self._intent_root

    @property
    # ID: b0e1d8c2-3f4a-4a2e-8c7a-9a8b7c6d5e4f
    def registry_path(self) -> Path:
        """
        Path to the master intent registry (path only).
        Kept because bootstrapping needs a stable anchor.
        """
        return self.intent_root / "schemas" / "META" / "intent_types.json"

    # =========================================================================
    # RUNTIME ROOTS (var/)
    # =========================================================================

    @property
    # ID: 3d6d3a0f-8e67-4e3c-9eaa-2c7b53b2a0c7
    def var_dir(self) -> Path:
        """Root directory for runtime state (var/)."""
        return self._repo_root / "var"

    @property
    # ID: 8e4a2c22-5f9e-4f3d-9b6b-8b1f8b4b3a1f
    def workflows_dir(self) -> Path:
        """Root directory for governed workflows (var/workflows/)."""
        return self._repo_root.joinpath(*self._DEFAULT_WORKFLOWS_SUBDIR)

    @property
    # ID: 7c52f9cb-5d8f-4c1c-9e1e-08f7b44f7b9f
    def build_dir(self) -> Path:
        """Directory for build artefacts (var/build/)."""
        return self._repo_root.joinpath(*self._DEFAULT_BUILD_SUBDIR)

    @property
    # ID: a5caa41d-7f34-4d1c-bd63-8b71df8c76bd
    def reports_dir(self) -> Path:
        """Directory for reports (var/reports/)."""
        return self._repo_root.joinpath(*self._DEFAULT_REPORTS_SUBDIR)

    @property
    # ID: 6f6a4a33-9e6f-4b26-b7ef-0f4f8c4dbcf3
    def logs_dir(self) -> Path:
        """Directory for logs (var/logs/)."""
        return self._repo_root.joinpath(*self._DEFAULT_LOGS_SUBDIR)

    @property
    # ID: 58d20e6e-7c3b-4d3c-a04a-6d75f86a0d6d
    def exports_dir(self) -> Path:
        """Directory for exports (var/exports/)."""
        return self._repo_root.joinpath(*self._DEFAULT_EXPORTS_SUBDIR)

    @property
    # ID: 5e8d4b18-11df-4fe8-b1b0-74d4c2d6f44a
    def context_dir(self) -> Path:
        """Directory containing runtime context artefacts (var/context)."""
        return self._repo_root.joinpath(*self._DEFAULT_CONTEXT_SUBDIR)

    @property
    # ID: 0b8f1bb0-2d5c-4ce5-8ad0-4d6e5a35f7a1
    def context_cache_dir(self) -> Path:
        """Directory containing disposable context cache (var/cache/context)."""
        return self._repo_root.joinpath(*self._DEFAULT_CONTEXT_CACHE_SUBDIR)

    # ID: 4a5a5d3e-8d54-4f07-9a31-08d2a2bb2f60
    def context_schema_path(self) -> Path:
        """Path to runtime context schema file."""
        return self.context_dir / "schema.yaml"

    @property
    # ID: 694858d4-5b4d-4e9e-8c3a-96942c7e87ab
    def knowledge_dir(self) -> Path:
        """Directory containing living knowledge state (var/mind/knowledge)."""
        return self._repo_root.joinpath(*self._DEFAULT_KNOWLEDGE_SUBDIR)

    @property
    # ID: 243ebce3-db6e-407e-9f53-7fd4669728b9
    def mind_export_dir(self) -> Path:
        """Directory for Mind state exports (var/core/mind_export)."""
        return self._repo_root / "var" / "core" / "mind_export"

    # ID: e631bf4f-5e70-491c-a685-fa87754af9cf
    def mind_export(self, resource: str) -> Path:
        """Get path to a Mind export file."""
        return self.mind_export_dir / f"{resource}.yaml"

    # =========================================================================
    # WORKFLOWS: well-known subdirs (var/workflows/*)
    # =========================================================================

    @property
    # ID: 6adf5f2e-761f-4ad5-bc59-cbcb40c39b69
    def proposals_dir(self) -> Path:
        return self.workflows_dir / "proposals"

    @property
    # ID: 18f6d4c1-9a83-4f50-8a1b-9c8201f7a6c1
    def pending_writes_dir(self) -> Path:
        return self.workflows_dir / "pending_writes"

    @property
    # ID: 5c5c4f71-8aa3-4c8c-8f39-1a9a33f0a3d2
    def canary_dir(self) -> Path:
        return self.workflows_dir / "canary"

    # =========================================================================
    # PROMPTS (var/prompts)
    # =========================================================================

    @property
    # ID: 2a4f2cb7-4b66-4d49-a7a0-4ab9a2c3c8f5
    def prompts_dir(self) -> Path:
        """Directory containing prompt templates (var/prompts)."""
        return self._repo_root.joinpath(*self._DEFAULT_PROMPTS_SUBDIR)

    # ID: 4f42c781-6d21-4c67-8b0a-7f9efb0f0f2b
    def prompt(self, name: str) -> Path:
        """Resolve a prompt template file path by stem (e.g., 'planner')."""
        safe = name.strip().replace("\\", "/").split("/")[-1]
        return self.prompts_dir / f"{safe}.prompt"

    # ID: ca8f8d94-eb47-4163-af8e-8baff04e716c
    def list_prompts(self) -> list[str]:
        """List available prompt templates (stems). No filesystem mutation."""
        if not self.prompts_dir.exists():
            return []
        return sorted({p.stem for p in self.prompts_dir.glob("*.prompt")})

    # =========================================================================
    # OTHER (non-governed scratch)
    # =========================================================================

    @property
    # ID: 78d4598f-1267-4607-b3fb-469f4f092a90
    def work_dir(self) -> Path:
        """Temporary human scratch directory (work/)."""
        return self._repo_root / "work"

    # =========================================================================
    # STRUCTURE VALIDATION (no mkdir)
    # =========================================================================

    # ID: 2374f137-6c7f-4ecc-a804-d3e8d18dd137
    def validate_structure(self) -> list[str]:
        """
        Validate expected directories exist.

        This method MUST NOT create directories. It reports missing ones, and the
        caller decides whether to create them via FileHandler or another governed
        mutation surface.

        Returns:
            List of missing-path messages (empty if all exist).
        """
        required_dirs: list[tuple[Path, str]] = [
            (self.var_dir, "var/"),
            (self.workflows_dir, "var/workflows/"),
            (self.canary_dir, "var/workflows/canary/"),
            (self.proposals_dir, "var/workflows/proposals/"),
            (self.pending_writes_dir, "var/workflows/pending_writes/"),
            (self.prompts_dir, "var/prompts/"),
            (self.context_dir, "var/context/"),
            (self.context_cache_dir, "var/cache/context/"),
            (self.knowledge_dir, "var/mind/knowledge/"),
            (self.logs_dir, "var/logs/"),
            (self.reports_dir, "var/reports/"),
            (self.exports_dir, "var/exports/"),
            (self.build_dir, "var/build/"),
        ]

        errors: list[str] = []
        for p, _label in required_dirs:
            if not p.exists():
                errors.append(str(p))

        # .intent is governance-managed; still report if missing.
        if not self.intent_root.exists():
            errors.append(str(self.intent_root))

        if errors:
            # Caller logs this already; keep message stable for upstream parsing.
            logger.debug(
                "PathResolver.validate_structure missing: %s", "; ".join(errors)
            )

        return errors

    def __repr__(self) -> str:
        return f"PathResolver(root={self._repo_root})"

    # =========================================================================
    # POLICY RESOLUTION (path only; no file reads)
    # =========================================================================

    # ID: f0cca605-cbd8-4007-a9d4-dba5598cc6ba
    def policy(self, policy_id: str) -> Path:
        """
        Resolve a policy file path under `.intent/policies/` by:
        - direct relative path (with or without extension), OR
        - stem lookup anywhere under policies/.

        This is path resolution only (no file reads), because many checks still
        require a stable `policy_file: ClassVar[Path]`.

        Args:
            policy_id: Policy stem (e.g. "code_standards") or relative path under
                      policies (e.g. "architecture/atomic_actions").

        Returns:
            Path to the matching policy file.

        Raises:
            FileNotFoundError: if not found.
        """
        policies_root = self.intent_root / "policies"
        raw = policy_id.strip().replace("\\", "/")
        raw = raw.removeprefix("policies/").removeprefix(".intent/policies/")

        # 1) Direct path
        direct = policies_root / raw
        if direct.suffix in {".json", ".yaml", ".yml"} and direct.exists():
            return direct

        for ext in (".json", ".yaml", ".yml"):
            cand = direct.with_suffix(ext)
            if cand.exists():
                return cand

        # 2) Stem scan anywhere under policies/
        name = Path(raw).name
        patterns = [
            str(policies_root / "**" / f"{name}.json"),
            str(policies_root / "**" / f"{name}.yaml"),
            str(policies_root / "**" / f"{name}.yml"),
        ]

        matches: list[str] = []
        for pat in patterns:
            matches.extend(glob.glob(pat, recursive=True))

        if not matches:
            available = sorted(
                {
                    Path(p).stem
                    for p in glob.glob(
                        str(policies_root / "**" / "*.*"), recursive=True
                    )
                    if Path(p).suffix in {".json", ".yaml", ".yml"}
                }
            )
            raise FileNotFoundError(
                f"Policy {policy_id!r} not found in {policies_root}. "
                f"Available policies: {', '.join(available)}"
            )

        return Path(sorted(matches)[0])
