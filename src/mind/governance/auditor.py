# src/mind/governance/auditor.py
"""
Constitutional Auditor - The Unified Enforcement Engine.

REFACTORED: 100% Dynamic Engine-based execution.
This module no longer crawls 'mind.governance.checks' for Python classes.
It relies exclusively on 'run_dynamic_rules' to execute policies declared in JSON.

Key outputs:
- reports/audit_findings.json
- reports/audit_findings.processed.json
- reports/audit/latest_audit.json (Authoritative Evidence Ledger)
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from body.cli.commands.audit_reporter import AuditRunReporter
from mind.governance.audit_context import AuditorContext
from mind.governance.audit_postprocessor import (
    EntryPointAllowList,
    apply_entry_point_downgrade_and_report,
)
from mind.governance.constitutional_auditor_dynamic import (
    get_dynamic_execution_stats,
    run_dynamic_rules,
)
from shared.activity_logging import activity_run, new_activity_run
from shared.infrastructure.storage.file_handler import FileHandler
from shared.logger import getLogger
from shared.models import AuditSeverity
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

    def __init__(self, context: AuditorContext):
        self.context = context
        # Governed mutation surface (IntentGuard enforced)
        self.fs = FileHandler(str(get_repo_root().resolve()))
        # Ensure output dirs exist
        self.fs.ensure_dir("reports")
        self.fs.ensure_dir("reports/audit")

    # ID: e70bf756-620a-4065-99df-34b03cc25c96
    async def run_full_audit_async(self) -> list[dict[str, Any]]:
        """
        Executes the full constitutional audit using the Dynamic Rule Engine.
        """
        await self.context.load_knowledge_graph()

        with activity_run("constitutional_audit"):
            run = new_activity_run("constitutional_audit")

            # We no longer discover classes, so we start with 0 legacy checks.
            reporter = AuditRunReporter(
                run=run,
                repo_path=get_repo_root(),
                total_checks=0,
            )

            executed_rule_ids: set[str] = set()

            # 1. CORE EXECUTION: Run dynamic rules from JSON policies
            logger.info("=== Running Dynamic Constitutional Enforcement ===")
            findings = await run_dynamic_rules(
                self.context, executed_rule_ids=executed_rule_ids
            )

            # 2. PERSISTENCE: Write raw findings
            findings_path = self._write_findings(findings)

            # 3. POST-PROCESSING: Apply severity downgrades
            symbol_index_path = REPORTS_DIR / SYMBOL_INDEX_FILENAME
            if not symbol_index_path.exists():
                self.fs.write_runtime_text(
                    _repo_rel(symbol_index_path),
                    json.dumps({}, indent=2),
                )

            processed_path = self._write_processed_findings(
                findings_path, symbol_index_path
            )

            # 4. DECISION: Determine pass/fail
            passed = not any(f.severity == AuditSeverity.ERROR for f in findings)

            # 5. EVIDENCE: Write the authoritative Evidence Ledger
            stats = get_dynamic_execution_stats(self.context, executed_rule_ids)
            logger.info("Audit stats: %s", stats)

            self._write_audit_evidence(
                executed_rules=executed_rule_ids,
                findings_path=findings_path,
                processed_findings_path=processed_path,
                passed=passed,
            )

            return [f.as_dict() for f in findings]

    def _write_findings(self, findings: list[Any]) -> Path:
        out_path = REPORTS_DIR / FINDINGS_FILENAME
        out_payload = [f.as_dict() for f in findings]
        self.fs.write_runtime_json(_repo_rel(out_path), out_payload)
        return out_path

    def _write_processed_findings(
        self, findings_path: Path, symbol_index_path: Path
    ) -> Path:
        out_path = REPORTS_DIR / PROCESSED_FINDINGS_FILENAME

        # apply_entry_point_downgrade_and_report handles its own reporting internal to the service
        processed = apply_entry_point_downgrade_and_report(
            findings=json.loads(findings_path.read_text(encoding="utf-8")),
            symbol_index=json.loads(symbol_index_path.read_text(encoding="utf-8")),
            reports_dir=REPORTS_DIR,
            allow_list=EntryPointAllowList.default(),
            dead_rule_ids=("dead_public_symbol", "dead-public-symbol"),
            downgrade_to=DOWNGRADE_SEVERITY_TO,
            write_reports=True,
            file_handler=self.fs,
            repo_root=get_repo_root(),
        )
        self.fs.write_runtime_json(_repo_rel(out_path), processed)
        return out_path

    def _write_audit_evidence(
        self,
        *,
        executed_rules: set[str],
        findings_path: Path,
        processed_findings_path: Path,
        passed: bool,
    ) -> Path:
        """Writes the evidence required by 'governance coverage' command."""
        evidence_path = AUDIT_EVIDENCE_DIR / AUDIT_EVIDENCE_FILENAME

        payload: dict[str, Any] = {
            "schema_version": "0.2.0",
            "generated_at_utc": _utc_now_iso(),
            "source": "core-admin check audit",
            "passed": passed,
            "artifacts": {
                "findings": _repo_rel(findings_path),
                "processed_findings": _repo_rel(processed_findings_path),
            },
            # FIXED: Use the argument name 'executed_rules'
            "executed_rules": sorted(list(executed_rules)),
            "executed_checks": [],  # Legacy checks removed
        }

        self.fs.write_runtime_json(_repo_rel(evidence_path), payload)
        return evidence_path
