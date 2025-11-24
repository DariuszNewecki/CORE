# src/mind/governance/auditor.py
"""
Constitutional Auditor — The primary orchestration engine for all governance checks.
"""

from __future__ import annotations

import asyncio
import importlib
import inspect
import json
import pkgutil
import time
from collections.abc import MutableMapping
from typing import Any

from mind.governance import checks
from mind.governance.audit_context import AuditorContext
from mind.governance.audit_postprocessor import (
    EntryPointAllowList,
    apply_entry_point_downgrade_and_report,
)
from mind.governance.checks.base_check import BaseCheck
from shared.logger import getLogger  # ✅ CORRECT logger import
from shared.models import AuditFinding, AuditSeverity
from shared.path_utils import get_repo_root

logger = getLogger(__name__)  # ✅ CORRECT logger instance

# --- Configuration for the Auditor ---
REPORTS_DIR = get_repo_root() / "reports"
FINDINGS_FILENAME = "audit_findings.json"
PROCESSED_FINDINGS_FILENAME = "audit_findings.processed.json"
SYMBOL_INDEX_FILENAME = "symbol_index.json"
DOWNGRADE_SEVERITY_TO = "info"
DEAD_SYMBOL_RULE_IDS = {"linkage.capability.unassigned"}


# ID: 420dc6e1-2b67-476f-aa6a-9cddd839304c
class ConstitutionalAuditor:
    """
    Orchestrates the constitutional audit by discovering and running all checks.
    """

    def __init__(self, context: AuditorContext):
        self.context = context
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    def _discover_checks(self) -> list[type[BaseCheck]]:
        """Dynamically discovers all BaseCheck subclasses in the checks package."""
        check_classes = []
        for _, name, _ in pkgutil.iter_modules(checks.__path__):
            module = importlib.import_module(f"mind.governance.checks.{name}")
            for item_name, item in inspect.getmembers(module, inspect.isclass):
                if (
                    issubclass(item, BaseCheck)
                    and item is not BaseCheck
                    and not inspect.isabstract(item)
                ):
                    check_classes.append(item)
        return check_classes

    async def _run_all_checks(self) -> tuple[list[AuditFinding], int]:
        """Instantiates and runs all discovered checks, collecting their findings."""
        all_findings: list[AuditFinding] = []
        check_classes = self._discover_checks()
        qdrant_service = None  # Lazy-initialized service placeholder

        for check_class in check_classes:
            check_instance = None

            # DuplicationCheck special-case
            if check_class.__name__ == "DuplicationCheck":
                if qdrant_service is None:
                    try:
                        from services.clients.qdrant_client import QdrantService

                        qdrant_service = QdrantService()
                    except Exception as e:
                        all_findings.append(
                            AuditFinding(
                                check_id="auditor.internal.error",
                                severity=AuditSeverity.ERROR,
                                message=f"Failed to initialize QdrantService for DuplicationCheck: {e}",
                            )
                        )
                        continue
                check_instance = check_class(self.context, qdrant_service)
            else:
                check_instance = check_class(self.context)

            # RUN CHECK
            start = time.perf_counter()  # ⏱️ Start timing
            if inspect.iscoroutinefunction(check_instance.execute):
                findings = await check_instance.execute()
            else:
                findings = await asyncio.to_thread(check_instance.execute)
            elapsed = time.perf_counter() - start

            logger.info(
                f"Audit: check {check_class.__name__} completed in {elapsed:.2f}s "
                f"with {len(findings)} findings."
            )

            all_findings.extend(findings)

        unassigned_count = len(
            [f for f in all_findings if f.check_id == "linkage.capability.unassigned"]
        )

        return all_findings, unassigned_count

    # ID: 0c34d8c4-1530-4095-be43-bec35f36d538
    async def run_full_audit_async(self) -> list[MutableMapping[str, Any]]:
        """
        The main entry point for running a full, orchestrated constitutional audit.
        """

        logger.info("Audit: starting (loading knowledge graph)...")
        start = time.perf_counter()
        await self.context.load_knowledge_graph()
        logger.info(
            "Audit: load_knowledge_graph finished in %.2f seconds",
            time.perf_counter() - start,
        )

        logger.info("Audit: running all checks...")
        checks_start = time.perf_counter()
        raw_findings_objects, unassigned_count = await self._run_all_checks()
        logger.info(
            "Audit: _run_all_checks finished in %.2f seconds (unassigned_count=%d)",
            time.perf_counter() - checks_start,
            unassigned_count,
        )

        raw_findings = [f.as_dict() for f in raw_findings_objects]

        symbol_index = {
            key: {
                "entry_point_type": data.get("entry_point_type"),
                "pattern_name": data.get("pattern_name"),
                "entry_point_justification": data.get("entry_point_justification"),
            }
            for key, data in self.context.symbols_map.items()
        }

        (REPORTS_DIR / FINDINGS_FILENAME).write_text(json.dumps(raw_findings, indent=2))
        (REPORTS_DIR / SYMBOL_INDEX_FILENAME).write_text(
            json.dumps(symbol_index, indent=2)
        )

        processed_findings = apply_entry_point_downgrade_and_report(
            findings=raw_findings,
            symbol_index=symbol_index,
            reports_dir=REPORTS_DIR,
            allow_list=EntryPointAllowList.default(),
            dead_rule_ids=DEAD_SYMBOL_RULE_IDS,
            downgrade_to=DOWNGRADE_SEVERITY_TO,
            write_reports=True,
        )

        (REPORTS_DIR / PROCESSED_FINDINGS_FILENAME).write_text(
            json.dumps(processed_findings, indent=2)
        )

        return processed_findings
