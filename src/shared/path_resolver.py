# src/shared/path_resolver.py
"""
PathResolver - Single source of truth for all repository-relative paths in CORE.

Key boundary rules:
- PathResolver RESOLVES paths only. It must not mutate the filesystem (mkdir, write, copy, delete).
- Filesystem mutations (including mkdir) belong to FileHandler.
- Aligned to search both 'policies/' and 'standards/' for constitutional rule discovery.

Design:
- Deterministic path construction.
- No side effects.

V2.7 ADDITIONS:
- remediation_map_path: canonical path to auto_remediation.yaml
- audit_findings_path: canonical path to raw audit findings
- audit_findings_processed_path: canonical path to processed audit findings
- governance_config_path: canonical path to governance_paths.yaml
- crawl_scopes_config_path: canonical path to crawl_scopes.yaml
- workers_dir: canonical path to .intent/workers/
These replace all hardcoded Path("...") constants in Body and Will layers.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

from shared.logger import getLogger
from shared.models.validation_result import ValidationResult


logger = getLogger(__name__)


# ID: 75006a3a-ed9f-4f99-b1dc-8217cb03ad9f
class PathResolver:
    """
    Resolves all repository-relative paths in CORE.

    Important:
        This class is NOT a filesystem manager. It must not create directories.
        Use FileHandler for mkdir/copy/write operations.
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
        """
        resolver = cls(repo_root=repo_root, meta=meta)
        if intent_root is not None:
            resolver._intent_root = Path(intent_root)
        return resolver

    def __init__(self, repo_root: Path, meta: dict[str, Any] | None = None):
        """
        Args:
            repo_root: Root directory of the CORE repository.
        """
        self._repo_root = Path(repo_root).resolve()
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
        """Path to the master intent registry."""
        return self.intent_root / "schemas" / "META" / "intent_types.json"

    # =========================================================================
    # RUNTIME ROOTS (var/)
    # =========================================================================

    @property
    # ID: 78a6f2cd-4f39-4840-afc0-83bc10c1d409
    def var_dir(self) -> Path:
        return self._repo_root / "var"

    @property
    # ID: d35865f7-b5f0-4e33-804e-cd7aa13f3cba
    def workflows_dir(self) -> Path:
        return self._repo_root.joinpath(*self._DEFAULT_WORKFLOWS_SUBDIR)

    @property
    # ID: f0f7057e-00f3-4a06-aa93-fd4152339da8
    def build_dir(self) -> Path:
        return self._repo_root.joinpath(*self._DEFAULT_BUILD_SUBDIR)

    @property
    # ID: 8f858176-f2d1-42ee-be36-79b70c35d3de
    def reports_dir(self) -> Path:
        return self._repo_root.joinpath(*self._DEFAULT_REPORTS_SUBDIR)

    @property
    # ID: 57b1229f-57f3-4d83-911a-55075081fae7
    def logs_dir(self) -> Path:
        return self._repo_root.joinpath(*self._DEFAULT_LOGS_SUBDIR)

    @property
    # ID: 63eff06a-930a-4df7-90be-8172116fc361
    def exports_dir(self) -> Path:
        return self._repo_root.joinpath(*self._DEFAULT_EXPORTS_SUBDIR)

    @property
    # ID: aad7047a-cbeb-475e-ac1a-3180eef745be
    def context_dir(self) -> Path:
        return self._repo_root.joinpath(*self._DEFAULT_CONTEXT_SUBDIR)

    @property
    # ID: f25e5afb-7bf4-4930-855a-fb2d84bfbd22
    def context_cache_dir(self) -> Path:
        return self._repo_root.joinpath(*self._DEFAULT_CONTEXT_CACHE_SUBDIR)

    # ID: 71eea8fd-38ae-4707-8dac-2ecc7a52af08
    def context_schema_path(self) -> Path:
        return self.context_dir / "schema.yaml"

    @property
    # ID: da01c682-35df-48d5-af6c-2a68a031b582
    def knowledge_dir(self) -> Path:
        return self._repo_root.joinpath(*self._DEFAULT_KNOWLEDGE_SUBDIR)

    @property
    # ID: 1430c7a5-c840-4416-97e2-0db14fbbc756
    def mind_export_dir(self) -> Path:
        return self._repo_root / "var" / "core" / "mind_export"

    # ID: 5a8d7abf-f560-41ed-ad72-6f9b12883489
    def mind_export(self, resource: str) -> Path:
        return self.mind_export_dir / f"{resource}.yaml"

    @property
    # ID: 3ee4afe4-510f-4ba3-b028-7ddff08cfcc6
    def proposals_dir(self) -> Path:
        return self.workflows_dir / "proposals"

    @property
    # ID: ad7b8a0f-55b9-4d4e-a07d-dc3624d782a4
    def pending_writes_dir(self) -> Path:
        return self.workflows_dir / "pending_writes"

    @property
    # ID: 27eac5a7-82d0-4f66-aa0f-f50949e562bb
    def canary_dir(self) -> Path:
        return self.workflows_dir / "canary"

    @property
    # ID: a665cb45-3f2d-42d2-ac93-4156468d007f
    def morgue_dir(self) -> Path:
        """Directory for quarantined/failed artifacts."""
        return self.workflows_dir / "morgue"

    @property
    # ID: c3d4e5f6-a7b8-9012-cdef-111111111111
    def prompts_dir(self) -> Path:
        return self._repo_root.joinpath(*self._DEFAULT_PROMPTS_SUBDIR)

    # =========================================================================
    # GOVERNANCE PATHS (V2.7)
    # These replace hardcoded Path("...") constants in Body and Will layers.
    # All governance-relevant paths are resolved here and nowhere else.
    # =========================================================================

    @property
    # ID: a1b2c3d4-e5f6-7890-abcd-ef0000000001
    def governance_config_path(self) -> Path:
        """
        Path to the constitutional governance paths & thresholds config.
        Source of truth for MIN_CONFIDENCE, audit findings paths, etc.
        File: .intent/enforcement/config/governance_paths.yaml
        """
        return self._intent_root / "enforcement" / "config" / "governance_paths.yaml"

    @property
    # ID: a1b2c3d4-e5f6-7890-abcd-ef0000000002
    def crawl_scopes_config_path(self) -> Path:
        """
        Path to the crawl scopes & Qdrant collection mapping config.
        Source of truth for RepoCrawlerWorker scopes and collection names.
        File: .intent/enforcement/config/crawl_scopes.yaml
        """
        return self._intent_root / "enforcement" / "config" / "crawl_scopes.yaml"

    @property
    # ID: a1b2c3d4-e5f6-7890-abcd-ef0000000003
    def remediation_map_path(self) -> Path:
        """
        Canonical path to the autonomous remediation mapping.
        Replaces: REMEDIATION_MAP_PATH = Path(".intent/enforcement/mappings/remediation/auto_remediation.yaml")
        in body/autonomy/audit_analyzer.py
        """
        return (
            self._intent_root
            / "enforcement"
            / "mappings"
            / "remediation"
            / "auto_remediation.yaml"
        )

    @property
    # ID: a1b2c3d4-e5f6-7890-abcd-ef0000000004
    def audit_findings_path(self) -> Path:
        """
        Canonical path to the raw audit findings JSON.
        Replaces: repo_root / "reports" / "audit_findings.json"
        in vulture_healer.py and AuditAnalyzer.
        """
        return self.reports_dir / "audit_findings.json"

    @property
    # ID: a1b2c3d4-e5f6-7890-abcd-ef0000000005
    def audit_findings_processed_path(self) -> Path:
        """
        Canonical path to the processed audit findings JSON.
        Replaces: repo_root / "reports" / "audit_findings.processed.json"
        in AuditRemediationService._default_findings_path().
        """
        return self.reports_dir / "audit_findings.processed.json"

    @property
    # ID: a1b2c3d4-e5f6-7890-abcd-ef0000000006
    def remediation_evidence_dir(self) -> Path:
        """
        Canonical directory for remediation evidence artifacts.
        Replaces: repo_root / "reports" / "remediation" in RemediationEvidenceWriter.
        """
        return self.reports_dir / "remediation"

    @property
    # ID: a1b2c3d4-e5f6-7890-abcd-ef0000000007
    def workers_dir(self) -> Path:
        """
        Canonical path to .intent/workers/ declarations.
        Replaces: Path(".intent/workers") in WorkerAuditor.
        """
        return self._intent_root / "workers"

    # =========================================================================
    # VALIDATION
    # =========================================================================

    # ID: 3f6e9c2a-1b4d-4e7f-8a0c-5d2e9b3c6a1f
    def validate_structure(self) -> ValidationResult:
        """
        Validate that the expected runtime directory structure exists.

        Returns:
            ValidationResult with ok=True if all required dirs exist.
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
        for p, label in required_dirs:
            if not p.exists():
                errors.append(f"Missing required directory: {label} (expected at {p})")

        if not self.intent_root.exists():
            errors.append(f"Missing constitutional intent root at {self.intent_root}")

        # Validate governance config files exist
        if not self.governance_config_path.exists():
            errors.append(
                f"Missing governance config: {self.governance_config_path} "
                "(create .intent/enforcement/config/governance_paths.yaml)"
            )

        if not self.crawl_scopes_config_path.exists():
            errors.append(
                f"Missing crawl scopes config: {self.crawl_scopes_config_path} "
                "(create .intent/enforcement/config/crawl_scopes.yaml)"
            )

        return ValidationResult(
            ok=not errors,
            errors=errors,
            metadata={"checked_paths": [str(p) for p, _ in required_dirs]},
        )

    def __repr__(self) -> str:
        return f"PathResolver(root={self._repo_root})"

    # =========================================================================
    # CONSTITUTIONAL RESOLUTION (Policies & Standards)
    # =========================================================================

    # ID: f0cca605-cbd8-4007-a9d4-dba5598cc6ba
    def policy(self, policy_id: str) -> Path:
        """
        Unified resolution for rule-bearing artifacts.
        Searches .intent/policies/ AND .intent/standards/.

        Args:
            policy_id: The stem or path fragment of the policy/standard.

        Returns:
            Absolute Path to the first matching file found.
        """
        search_roots = [
            self.intent_root / "policies",
            self.intent_root / "standards",
            self.intent_root / "rules",
        ]

        raw = policy_id.replace("\\", "/").strip().lstrip("/")
        for prefix in ("policies/", "standards/", ".intent/"):
            if raw.startswith(prefix):
                raw = raw[len(prefix) :]

        for root in search_roots:
            direct = root / raw
            for ext in (".json", ".yaml", ".yml", ""):
                p = direct.with_suffix(ext) if ext else direct
                if p.is_file() and p.exists():
                    return p

        stem = Path(raw).name
        for root in search_roots:
            if not root.exists():
                continue
            for ext in (".json", ".yaml", ".yml"):
                matches = list(root.rglob(f"{stem}{ext}"))
                if matches:
                    return matches[0]

        raise FileNotFoundError(
            f"Policy '{policy_id}' not found in {[str(r) for r in search_roots]}"
        )

    # ID: 9a3f6c2e-1b4d-4e7f-8a0c-5d2e9b3c6a1f
    def workflow(self, workflow_id: str) -> Path:
        """Resolve a workflow definition YAML from .intent/workflows/."""
        base = self.intent_root / "workflows"
        for subdir in ("definitions", ""):
            candidate = base / subdir / f"{workflow_id}.yaml"
            if candidate.exists():
                return candidate
        raise FileNotFoundError(f"Workflow '{workflow_id}' not found under {base}")

    # ID: 8b2e5a1c-3d6f-4e7a-9b0c-2d5e8a3c7b1e
    def phase(self, phase_id: str) -> Path:
        """Resolve a phase definition YAML from .intent/phases/."""
        candidate = self.intent_root / "phases" / f"{phase_id}.yaml"
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"Phase '{phase_id}' not found at {candidate}")
