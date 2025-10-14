# src/features/governance/constitutional_auditor.py
"""
Constitutional Auditor — The primary orchestration engine for all governance checks.

This refactored version implements a dynamic discovery and execution pipeline for
all audit checks defined in the `src/features/governance/checks/` directory.

Pipeline:
  1. Discover all check classes that inherit from BaseCheck.
  2. Instantiate and execute each check, collecting all raw findings.
  3. Apply entry-point-aware post-processing to downgrade severities for
     valid entry points (e.g., CLI commands, data models).
  4. Persist all raw and processed artifacts to the /reports directory.
"""

from __future__ import annotations

import asyncio
import importlib
import inspect
import json
import pkgutil
from typing import (
    Any,
    Dict,
    List,
    MutableMapping,
    Optional,
    Tuple,
)

from shared.models import AuditFinding
from shared.path_utils import get_repo_root

from features.governance import checks
from features.governance.audit_context import AuditorContext
from features.governance.audit_postprocessor import (
    EntryPointAllowList,
    apply_entry_point_downgrade_and_report,
)
from features.governance.checks.base_check import BaseCheck

# --- Configuration for the Auditor ---
REPORTS_DIR = get_repo_root() / "reports"
FINDINGS_FILENAME = "audit_findings.json"
PROCESSED_FINDINGS_FILENAME = "audit_findings.processed.json"
SYMBOL_INDEX_FILENAME = "symbol_index.json"
DOWNGRADE_SEVERITY_TO = "info"
DEAD_SYMBOL_RULE_IDS = {"linkage.capability.unassigned"}


# ID: 12c75fea-ee99-4d3d-ade6-8b9d086f6e89
class ConstitutionalAuditor:
    """
    Orchestrates the constitutional audit by discovering and running all checks.
    """

    def __init__(self, context: AuditorContext):
        self.context = context
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    def _discover_checks(self) -> List[type[BaseCheck]]:
        """Dynamically discovers all BaseCheck subclasses in the checks package."""
        check_classes = []
        for _, name, _ in pkgutil.iter_modules(checks.__path__):
            module = importlib.import_module(f"features.governance.checks.{name}")
            for item_name, item in inspect.getmembers(module, inspect.isclass):
                if (
                    issubclass(item, BaseCheck)
                    and item is not BaseCheck
                    and not inspect.isabstract(item)
                ):
                    check_classes.append(item)
        return check_classes

    async def _run_all_checks(self) -> Tuple[List[AuditFinding], int]:
        """Instantiates and runs all discovered checks, collecting their findings."""
        all_findings: List[AuditFinding] = []
        check_classes = self._discover_checks()

        for check_class in check_classes:
            check_instance = check_class(self.context)

            # --- THIS IS THE FIX ---
            # Intelligently handle both sync and async execute methods.
            if inspect.iscoroutinefunction(check_instance.execute):
                # If it's an `async def`, await it directly.
                findings = await check_instance.execute()
            else:
                # If it's a regular `def`, run it in a thread to avoid blocking.
                findings = await asyncio.to_thread(check_instance.execute)
            # --- END OF FIX ---

            all_findings.extend(findings)

        unassigned_count = len(
            [f for f in all_findings if f.check_id == "linkage.capability.unassigned"]
        )

        return all_findings, unassigned_count

    # ID: 32160d41-0c9c-4e43-ba55-9994b857eb76
    async def run_full_audit_async(self) -> List[MutableMapping[str, Any]]:
        """
        The main entry point for running a full, orchestrated constitutional audit.
        """
        # Ensure the knowledge graph is loaded, as all checks depend on it.
        await self.context.load_knowledge_graph()

        # Run all individual check classes to get raw findings.
        raw_findings_objects, unassigned_count = await self._run_all_checks()
        raw_findings = [f.as_dict() for f in raw_findings_objects]

        # Build the symbol index for the post-processor.
        symbol_index = {
            key: {
                "entry_point_type": data.get("entry_point_type"),
                "pattern_name": data.get("pattern_name"),
                "entry_point_justification": data.get("entry_point_justification"),
            }
            for key, data in self.context.symbols_map.items()
        }

        # Persist the raw artifacts for debugging and traceability.
        (REPORTS_DIR / FINDINGS_FILENAME).write_text(json.dumps(raw_findings, indent=2))
        (REPORTS_DIR / SYMBOL_INDEX_FILENAME).write_text(
            json.dumps(symbol_index, indent=2)
        )

        # Apply the intelligent post-processing to downgrade valid entry points.
        processed_findings = apply_entry_point_downgrade_and_report(
            findings=raw_findings,
            symbol_index=symbol_index,
            reports_dir=REPORTS_DIR,
            allow_list=EntryPointAllowList.default(),
            dead_rule_ids=DEAD_SYMBOL_RULE_IDS,
            downgrade_to=DOWNGRADE_SEVERITY_TO,
            write_reports=True,
        )

        # Persist the final, processed findings.
        (REPORTS_DIR / PROCESSED_FINDINGS_FILENAME).write_text(
            json.dumps(processed_findings, indent=2)
        )

        return processed_findings


# For backward compatibility with the CLI layer that expects a function
# This part of the file is left unchanged
# ID: 115bf540-765e-4620-9b4e-7cb9efae908e
def run_full_audit(
    context: Any, *, config: Optional[Dict] = None
) -> List[MutableMapping[str, Any]]:
    auditor = ConstitutionalAuditor(context)
    return asyncio.run(auditor.run_full_audit_async())


# ID: 531a4409-4ae2-4dbd-af30-33215d28f311
async def run_full_audit_async(
    context: Any, *, config: Optional[Dict] = None
) -> List[MutableMapping[str, Any]]:
    auditor = ConstitutionalAuditor(context)
    return await auditor.run_full_audit_async()
