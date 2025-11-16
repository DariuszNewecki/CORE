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
from collections.abc import MutableMapping
from typing import Any

from shared.models import AuditFinding
from shared.path_utils import get_repo_root

from mind.governance import checks
from mind.governance.audit_context import AuditorContext
from mind.governance.audit_postprocessor import (
    EntryPointAllowList,
    apply_entry_point_downgrade_and_report,
)
from mind.governance.checks.base_check import BaseCheck

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

        for check_class in check_classes:
            # === START OF FIX ===
            # Inject dependencies based on the check's specific needs.
            if check_class.__name__ == "DuplicationCheck":
                # The DuplicationCheck has a special dependency on QdrantService.
                # We get it from the context and pass it in during instantiation.
                if not hasattr(self.context, "qdrant_service"):
                    # This is an internal error state, but we handle it gracefully.
                    all_findings.append(
                        AuditFinding(
                            check_id="auditor.internal.error",
                            severity="error",
                            message="AuditorContext is missing qdrant_service. Cannot run DuplicationCheck.",
                        )
                    )
                    continue
                check_instance = check_class(self.context, self.context.qdrant_service)
            else:
                # Standard checks only need the context.
                check_instance = check_class(self.context)
            # === END OF FIX ===

            if inspect.iscoroutinefunction(check_instance.execute):
                findings = await check_instance.execute()
            else:
                findings = await asyncio.to_thread(check_instance.execute)
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
        await self.context.load_knowledge_graph()
        raw_findings_objects, unassigned_count = await self._run_all_checks()
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


# === START OF FIX: REMOVE REDUNDANT AND VIOLATING HELPER FUNCTIONS ===
# The functions below created new instances of ConstitutionalAuditor, which
# violated the DI policy. The correct pattern is to create the instance
# in the CLI layer (which is already being done) and call its methods.
# These functions are no longer needed.
# === END OF FIX ===
