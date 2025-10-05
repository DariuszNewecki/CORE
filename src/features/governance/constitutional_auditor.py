# src/features/governance/constitutional_auditor.py
"""
The Constitutional Auditor is the primary enforcement mechanism for the CORE constitution.
It runs a series of checks to ensure the codebase and its declared intent are aligned.
"""

from __future__ import annotations

import asyncio
import os
from enum import Enum, auto
from pathlib import Path
from typing import Any, List, Tuple

from rich.console import Console
from services.database.session_manager import get_session
from shared.config import settings
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    async_sessionmaker,
)

from features.governance.audit_context import AuditorContext

# --- START OF FIX: Remove the import for the obsolete check ---
# from features.governance.checks.capability_coverage import CapabilityCoverageCheck
# --- END OF FIX ---
from features.governance.checks.domain_placement import DomainPlacementCheck
from features.governance.checks.duplication_check import DuplicationCheck
from features.governance.checks.environment_checks import EnvironmentChecks
from features.governance.checks.file_checks import FileChecks
from features.governance.checks.health_checks import HealthChecks
from features.governance.checks.id_coverage_check import IdCoverageCheck
from features.governance.checks.id_uniqueness_check import IdUniquenessCheck
from features.governance.checks.import_rules import ImportRulesCheck
from features.governance.checks.manifest_lint import ManifestLintCheck
from features.governance.checks.naming_conventions import NamingConventionsCheck
from features.governance.checks.orphaned_logic import OrphanedLogicCheck
from features.governance.checks.security_checks import SecurityChecks
from features.governance.checks.style_checks import StyleChecks

log = getLogger("constitutional_auditor")
console = Console()


# ID: 792c49ce-1ca9-407a-948a-f355d0b4d75e
class AuditScope(Enum):
    """Defines the scope of an audit, allowing for targeted check execution."""

    FULL = auto()
    STATIC_ONLY = auto()


async def _get_async_engine() -> AsyncEngine:
    async with get_session() as session:
        try:
            conn = await session.connection()
            if isinstance(conn, AsyncConnection):
                return conn.engine
        except Exception:
            pass
        try:
            bind = session.get_bind()
        except Exception:
            bind = None
        if isinstance(bind, AsyncEngine):
            return bind
        if isinstance(bind, AsyncConnection):
            return bind.engine
        engine = getattr(bind, "engine", None)
        if isinstance(engine, AsyncEngine):
            return engine
        maybe_engine = getattr(session, "bind", None)
        if isinstance(maybe_engine, AsyncEngine):
            return maybe_engine
        if hasattr(session, "sync_session"):
            sync_bind = getattr(session.sync_session, "bind", None)
            if hasattr(sync_bind, "engine"):
                eng = getattr(sync_bind, "engine")
                if isinstance(eng, AsyncEngine):
                    return eng
    raise RuntimeError(
        "Could not acquire AsyncEngine from session manager for KnowledgeSourceCheck."
    )


async def _build_knowledge_source_check(context) -> Any | None:
    try:
        from features.governance.checks.knowledge_source_check import (
            CheckResult,
            KnowledgeSourceCheck,
        )
    except Exception:
        log.warning("KnowledgeSourceCheck not available; skipping this audit.")
        return None, None

    try:
        engine = await _get_async_engine()
    except Exception as e:
        log.warning(f"KnowledgeSourceCheck disabled (no DB engine): {e}")
        return None, None

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    repo_root = Path(settings.REPO_PATH)
    require_yaml = os.getenv("CORE_REQUIRE_YAML_EXPORTS") == "1"

    try:
        return (
            KnowledgeSourceCheck(
                repo_root=repo_root,
                engine=engine,
                session_factory=session_factory,
                reports_dir=repo_root / "reports" / "knowledge_ssot",
                require_yaml_exports=require_yaml,
            ),
            CheckResult,
        )
    except Exception as e:
        log.warning(f"KnowledgeSourceCheck initialization failed; skipping: {e}")
        return None, None


# ID: d12f0883-6304-432a-b778-e7c86c42dbd9
class ConstitutionalAuditor:
    """Orchestrates all constitutional checks and reports the findings."""

    def __init__(self, repo_root_override: Path | AuditorContext | None = None):
        if isinstance(repo_root_override, AuditorContext):
            self.context = repo_root_override
            self.repo_root = self.context.repo_path
        else:
            self.repo_root = repo_root_override or Path(".").resolve()
            self.context = AuditorContext(self.repo_root)
        self.all_checks: List[Any] = []
        self.CheckResultType = None

    async def _initialize_checks(self):
        """Initializes all checks after the context has loaded its async data."""
        if self.all_checks:
            return
        await self.context.load_knowledge_graph()

        ksrc_check, self.CheckResultType = await _build_knowledge_source_check(
            self.context
        )

        checks: List[Any] = [
            FileChecks(self.context),
            EnvironmentChecks(self.context),
            HealthChecks(self.context),
            StyleChecks(self.context),
            SecurityChecks(self.context),
            # --- START OF FIX: Remove the obsolete check ---
            # CapabilityCoverageCheck(self.context),
            # --- END OF FIX ---
            DomainPlacementCheck(self.context),
            ManifestLintCheck(self.context),
            ImportRulesCheck(self.context),
            NamingConventionsCheck(self.context),
            OrphanedLogicCheck(self.context),
            DuplicationCheck(self.context),
            ksrc_check,
            IdCoverageCheck(self.context),
            IdUniquenessCheck(self.context),
        ]
        self.all_checks = [c for c in checks if c is not None]
        log.info(
            f"ConstitutionalAuditor initialized with {len(self.all_checks)} total checks."
        )

    def _get_checks_for_scope(self, scope: AuditScope) -> List[Any]:
        """Filters the list of checks based on the requested audit scope."""
        if scope == AuditScope.FULL:
            return self.all_checks
        if scope == AuditScope.STATIC_ONLY:
            excluded_checks = (EnvironmentChecks, DuplicationCheck)
            return [
                check
                for check in self.all_checks
                if not isinstance(check, excluded_checks)
            ]
        return []

    # ID: 56da0f34-e75a-46d5-aeb2-e6d42fe978a6
    async def run_full_audit_async(
        self, scope: AuditScope = AuditScope.FULL
    ) -> Tuple[bool, List[AuditFinding], int]:
        """Asynchronously runs all registered checks for a given scope and returns the results."""
        await self._initialize_checks()
        checks_to_run = self._get_checks_for_scope(scope)
        log.info(
            f"Running audit with scope '{scope.name}' ({len(checks_to_run)} checks)..."
        )
        all_findings: List[AuditFinding] = []
        for check in checks_to_run:
            try:
                if asyncio.iscoroutinefunction(getattr(check, "execute", None)):
                    findings = await check.execute()
                else:
                    findings = check.execute()

                if self.CheckResultType and isinstance(findings, self.CheckResultType):
                    if not findings.passed:
                        all_findings.append(
                            AuditFinding(
                                check_id="knowledge.source.drift_detected",
                                severity=AuditSeverity.ERROR,
                                message="Drift detected between database and YAML knowledge files. See reports/knowledge_ssot for details.",
                                file_path=".intent/mind/knowledge/",
                            )
                        )
                elif findings:
                    all_findings.extend(findings)

            except Exception as e:
                log.error(
                    f"Error executing check '{type(check).__name__}': {e}",
                    exc_info=True,
                )

        ignore_policy = self.context.policies.get("audit_ignore_policy", {})
        path_ignores = [
            p.get("path") for p in ignore_policy.get("ignores", []) if p.get("path")
        ]
        symbol_ignores = {
            s.get("key")
            for s in ignore_policy.get("symbol_ignores", [])
            if s.get("key")
        }

        final_findings = []
        for finding in all_findings:
            is_ignored = False
            if finding.file_path and any(
                Path(finding.file_path).match(p) for p in path_ignores
            ):
                is_ignored = True

            if any(key in finding.message for key in symbol_ignores):
                is_ignored = True

            if not is_ignored:
                final_findings.append(finding)

        unassigned_symbols_count = len(
            OrphanedLogicCheck(self.context).find_unassigned_public_symbols()
        )
        has_errors = any(f.severity.is_blocking for f in final_findings)

        return not has_errors, final_findings, unassigned_symbols_count

    # ID: 08c9ab81-398d-4571-9220-328569adc293
    def run_full_audit(
        self, scope: AuditScope = AuditScope.FULL
    ) -> Tuple[bool, List[AuditFinding], int]:
        """Synchronous wrapper to run the full async audit for a given scope."""
        return asyncio.run(self.run_full_audit_async(scope))
