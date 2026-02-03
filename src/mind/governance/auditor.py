# src/mind/governance/auditor.py
# ID: 85bb69ce-b22a-490a-8a1d-92a5da7e2646

"""
Constitutional Auditor - The Unified Enforcement Engine.

CONSTITUTIONAL FIX:
- Uses service_registry.session() instead of get_session()
- NO LONGER imports FileHandler - uses FileService from Body layer

HEALED (V2.6.6):
- SAWarning Fix: Explicitly nullifies db_session in 'finally' block.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from body.services.file_service import FileService
from body.services.service_registry import service_registry
from mind.governance.audit_context import AuditorContext
from mind.governance.audit_postprocessor import (
    EntryPointAllowList,
    apply_entry_point_downgrade_and_report,
)
from mind.governance.constitutional_auditor_dynamic import (
    get_dynamic_execution_stats,
    run_dynamic_rules,
)
from mind.logic.engines.registry import EngineRegistry
from shared.activity_logging import ActivityRun, activity_run, new_activity_run
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity
from shared.path_utils import get_repo_root


logger = getLogger(__name__)

# --- Configuration ---
REPORTS_DIR = get_repo_root() / "reports"
FINDINGS_FILENAME = "audit_findings.json"
PROCESSED_FINDINGS_FILENAME = "audit_findings.processed.json"
SYMBOL_INDEX_FILENAME = "symbol_index.json"
DOWNGRADE_SEVERITY_TO = "info"

# Evidence artifact path
AUDIT_EVIDENCE_DIR = REPORTS_DIR / "audit"
AUDIT_EVIDENCE_FILENAME = "latest_audit.json"


def _utc_now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _repo_rel(path: Path) -> str:
    """Convert absolute path under repo root into a repo-relative string."""
    repo_root = get_repo_root().resolve()
    p = path.resolve()
    try:
        rel = p.relative_to(repo_root)
    except ValueError as e:
        raise ValueError(f"Path escapes repo boundary: {p}") from e
    return str(rel).lstrip("./")


# ID: 85bb69ce-b22a-490a-8a1d-92a5da7e2646
class ConstitutionalAuditor:
    """
    Orchestrates the constitutional audit by executing dynamic rules via engines.
    """

    def __init__(
        self, context: AuditorContext, file_service: FileService | None = None
    ):
        self.context = context
        self.fs = file_service or FileService(get_repo_root().resolve())
        self.fs.ensure_dir("reports")
        self.fs.ensure_dir("reports/audit")

    # ID: e70bf756-620a-4065-99df-34b03cc25c96
    async def run_full_audit_async(self) -> list[AuditFinding]:
        """
        Executes the full constitutional audit.
        """
        await self.context.load_knowledge_graph()

        with activity_run("constitutional_audit"):
            run = new_activity_run("constitutional_audit")
            executed_rule_ids: set[str] = set()

            # CONSTITUTIONAL FIX: Use the Body-owned session factory
            async with service_registry.session() as session:
                logger.info("=== Running Dynamic Constitutional Enforcement ===")

                # JIT Service Injection
                self.context.db_session = session

                if not getattr(self.context, "qdrant_service", None):
                    self.context.qdrant_service = (
                        await service_registry.get_qdrant_service()
                    )

                EngineRegistry.initialize(self.context.paths)

                try:
                    findings = await run_dynamic_rules(
                        self.context, executed_rule_ids=executed_rule_ids
                    )
                finally:
                    # HEALED: Explicitly nullify session to release connection to pool
                    if hasattr(self.context, "db_session"):
                        self.context.db_session = None

            # 2. PERSISTENCE
            findings_path = self._write_findings(findings)

            # 3. POST-PROCESSING
            symbol_index_path = REPORTS_DIR / SYMBOL_INDEX_FILENAME
            if not symbol_index_path.exists():
                self.fs.write_file(
                    _repo_rel(symbol_index_path), json.dumps({}, indent=2)
                )

            processed_path = self._write_processed_findings(
                findings_path, symbol_index_path
            )

            # 4. DECISION
            passed = not any(
                (f.severity if hasattr(f, "severity") else AuditSeverity.INFO)
                == AuditSeverity.ERROR
                for f in findings
            )

            # 5. EVIDENCE
            self._write_audit_evidence(findings, run, passed)

            # 6. STATS
            stats = get_dynamic_execution_stats(self.context, executed_rule_ids)
            logger.info("Dynamic Execution: %s", stats)

            return findings

    def _write_findings(self, findings: list) -> Path:
        path = REPORTS_DIR / FINDINGS_FILENAME
        findings_dicts = [f.as_dict() if hasattr(f, "as_dict") else f for f in findings]
        self.fs.write_file(_repo_rel(path), json.dumps(findings_dicts, indent=2))
        logger.info("Raw findings written to: %s", path)
        return path

    def _write_processed_findings(
        self, findings_path: Path, symbol_index_path: Path
    ) -> Path:
        findings_data = json.loads(findings_path.read_text())
        symbol_index_data = json.loads(symbol_index_path.read_text())

        processed_findings = apply_entry_point_downgrade_and_report(
            findings=findings_data,
            symbol_index=symbol_index_data,
            reports_dir=REPORTS_DIR,
            allow_list=EntryPointAllowList.default(),
            downgrade_to=DOWNGRADE_SEVERITY_TO,
            write_reports=True,
            file_service=self.fs,
            repo_root=get_repo_root(),
        )

        path = REPORTS_DIR / PROCESSED_FINDINGS_FILENAME
        self.fs.write_file(_repo_rel(path), json.dumps(processed_findings, indent=2))
        logger.info("Processed findings written to: %s", path)
        return path

    def _write_audit_evidence(
        self, findings: list, run: ActivityRun, passed: bool
    ) -> None:
        self.fs.ensure_dir(str(AUDIT_EVIDENCE_DIR.relative_to(get_repo_root())))
        evidence = {
            "audit_id": run.run_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "passed": passed,
            "findings_count": len(findings),
        }
        evidence_path = AUDIT_EVIDENCE_DIR / AUDIT_EVIDENCE_FILENAME
        self.fs.write_file(_repo_rel(evidence_path), json.dumps(evidence, indent=2))
        logger.info("Audit evidence written to: %s", evidence_path)
