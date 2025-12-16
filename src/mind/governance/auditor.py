# src/mind/governance/auditor.py
"""
Constitutional Auditor – The primary orchestration engine for all governance checks.

Discovers and runs all registered audit checks, coordinating their findings into
a single, comprehensive report. Emits evidence artifacts for downstream tools.

Key outputs (legacy, unchanged):
- reports/audit_findings.json
- reports/audit_findings.processed.json

New output (evidence, authoritative):
- reports/audit/latest_audit.json
  Contains executed_checks for *all* checks that were executed, even if they
  produced zero findings. This enables truthful enforcement coverage reporting.

CONSTITUTIONAL FIX: Now extracts policy_rule_ids from checks to properly track
which constitutional rules are enforced, not just which check classes ran.
"""

from __future__ import annotations

import asyncio
import importlib
import inspect
import json
import pkgutil
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mind.governance import checks
from mind.governance.audit_context import AuditorContext
from mind.governance.audit_postprocessor import (
    EntryPointAllowList,
    apply_entry_point_downgrade_and_report,
)
from mind.governance.audit_reporter import AuditRunReporter
from mind.governance.audit_types import AuditCheckMetadata, AuditCheckResult
from mind.governance.checks.base_check import BaseCheck
from shared.activity_logging import activity_run, new_activity_run
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
DEAD_SYMBOL_RULE_IDS = {"linkage.capability.unassigned"}

# New: stable evidence artifact path
AUDIT_EVIDENCE_DIR = REPORTS_DIR / "audit"
AUDIT_EVIDENCE_FILENAME = "latest_audit.json"


def _utc_now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _safe_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(path)


def _git_commit_sha(repo_root: Path) -> str | None:
    """
    Best-effort commit SHA. Avoids hard dependency on git.
    """
    try:
        import subprocess

        return (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                cwd=repo_root,
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )
    except Exception:
        return None


def _check_metadata_id(check_cls: type[BaseCheck]) -> str | None:
    meta: AuditCheckMetadata | None = getattr(check_cls, "metadata", None)
    if meta and isinstance(meta.id, str) and meta.id.strip():
        return meta.id.strip()
    return None


def _maybe_call(
    obj: Any, method_names: tuple[str, ...], *args: Any, **kwargs: Any
) -> bool:
    """
    Compatibility shim for evolving reporter APIs.

    Calls the first method name that exists on obj and is callable.
    Returns True if a method was called, otherwise False.
    """
    for name in method_names:
        meth = getattr(obj, name, None)
        if callable(meth):
            meth(*args, **kwargs)
            return True
    return False


# ID: 85bb69ce-b22a-490a-8a1d-92a5da7e2646
class ConstitutionalAuditor:
    """
    Orchestrates the constitutional audit by discovering and running all checks.
    """

    def __init__(self, context: AuditorContext):
        self.context = context
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    def _discover_checks(self) -> list[type[BaseCheck]]:
        """Dynamically discovers all BaseCheck subclasses in the checks package."""
        check_classes: list[type[BaseCheck]] = []
        for _, name, _ in pkgutil.iter_modules(checks.__path__):
            module = importlib.import_module(f"mind.governance.checks.{name}")
            for _, item in inspect.getmembers(module, inspect.isclass):
                if (
                    issubclass(item, BaseCheck)
                    and item is not BaseCheck
                    and not inspect.isabstract(item)
                ):
                    check_classes.append(item)
        return check_classes

    async def _run_all_checks(
        self,
        check_classes: list[type[BaseCheck]],
        reporter: AuditRunReporter,
        executed_ids: set[str],
    ) -> tuple[list[AuditFinding], int]:
        """
        Instantiates and runs all discovered checks, collecting their findings.

        executed_ids is mutated to include:
        - metadata ids for checks that ran (preferred)
        - policy_rule_ids from checks (constitutional rules enforced)
        - fallback to class name if neither metadata nor policy_rule_ids exist
        - any finding.check_id observed during execution
        """
        all_findings: list[AuditFinding] = []

        # Lazy service placeholder (checks requiring services should handle None or use registry)
        qdrant_service = None

        for check_class in check_classes:
            check_instance: BaseCheck | None = None

            # Record executed check identity (even if it yields zero findings)
            # CONSTITUTIONAL FIX: Extract policy_rule_ids to track which rules are enforced
            meta_id = _check_metadata_id(check_class)
            if meta_id:
                executed_ids.add(meta_id)
            elif hasattr(check_class, "policy_rule_ids") and isinstance(
                check_class.policy_rule_ids, list
            ):
                # Add all policy rule IDs this check enforces
                for rule_id in check_class.policy_rule_ids:
                    if isinstance(rule_id, str) and rule_id.strip():
                        executed_ids.add(rule_id.strip())
            else:
                executed_ids.add(check_class.__name__)

            start = time.perf_counter()
            try:
                # Instantiate checks
                # Some checks may require extra deps; keep behavior compatible with prior versions.
                try:
                    check_instance = check_class(self.context)  # type: ignore[call-arg]
                except TypeError:
                    # Backward-compat: checks that expect (context, qdrant_service)
                    check_instance = check_class(self.context, qdrant_service)  # type: ignore[call-arg]

                if inspect.iscoroutinefunction(check_instance.execute):
                    findings = await check_instance.execute()
                else:
                    findings = await asyncio.to_thread(check_instance.execute)

                # Collect findings + executed ids from findings themselves
                for f in findings:
                    if isinstance(f.check_id, str) and f.check_id.strip():
                        executed_ids.add(f.check_id.strip())

                all_findings.extend(findings)

                duration = time.perf_counter() - start
                reporter.record_check_result(
                    AuditCheckResult.from_raw(check_class, findings, duration)
                )
            except Exception as e:
                duration = time.perf_counter() - start
                logger.error(
                    "Audit check failed: %s (%s)",
                    check_class.__name__,
                    e,
                    exc_info=True,
                )

                # Produce an auditor-internal finding (keeps system truthful)
                internal = AuditFinding(
                    check_id="auditor.internal.error",
                    severity="error",
                    message=f"Check '{check_class.__name__}' raised exception: {e}",
                )
                all_findings.append(internal)

                reporter.record_check_result(
                    AuditCheckResult(
                        name=getattr(
                            getattr(check_class, "metadata", None), "name", None
                        )
                        or check_class.__name__,
                        category=getattr(
                            getattr(check_class, "metadata", None), "category", None
                        ),
                        duration_sec=duration,
                        findings_count=1,
                        max_severity=AuditSeverity.ERROR,
                        fix_hint=None,
                        extra={"exception": str(e)},
                    )
                )

        unassigned_count = len(
            [f for f in all_findings if f.check_id == "linkage.capability.unassigned"]
        )

        return all_findings, unassigned_count

    def _write_findings(self, findings: list[AuditFinding]) -> Path:
        out_path = REPORTS_DIR / FINDINGS_FILENAME
        out_payload = [f.as_dict() for f in findings]
        out_path.write_text(json.dumps(out_payload, indent=2), encoding="utf-8")
        return out_path

    def _write_processed_findings(
        self, findings_path: Path, symbol_index_path: Path
    ) -> Path:
        out_path = REPORTS_DIR / PROCESSED_FINDINGS_FILENAME

        processed = apply_entry_point_downgrade_and_report(
            findings=json.loads(findings_path.read_text(encoding="utf-8")),
            symbol_index=json.loads(symbol_index_path.read_text(encoding="utf-8")),
            reports_dir=REPORTS_DIR,
            allow_list=EntryPointAllowList.default(),
            dead_rule_ids=tuple(DEAD_SYMBOL_RULE_IDS),
            downgrade_to=DOWNGRADE_SEVERITY_TO,
            write_reports=True,
        )
        out_path.write_text(json.dumps(processed, indent=2), encoding="utf-8")
        return out_path

    def _write_audit_evidence(
        self,
        *,
        executed_checks: set[str],
        findings_path: Path,
        processed_findings_path: Path,
        passed: bool,
    ) -> Path:
        """
        Emit an authoritative evidence record for downstream governance reporting.
        """
        evidence_path = AUDIT_EVIDENCE_DIR / AUDIT_EVIDENCE_FILENAME

        payload: dict[str, Any] = {
            "schema_version": "0.1.0",
            "generated_at_utc": _utc_now_iso(),
            "source": "core-admin check audit",
            "repository_commit": _git_commit_sha(get_repo_root()),
            "passed": passed,
            "artifacts": {
                "findings": str(findings_path.relative_to(get_repo_root())),
                "processed_findings": str(
                    processed_findings_path.relative_to(get_repo_root())
                ),
            },
            "executed_checks": sorted(executed_checks),
        }

        _safe_write_json(evidence_path, payload)
        return evidence_path

    # ID: 178b5c18-373c-4d39-be91-9c71f37f4a23
    async def run_full_audit_async(self) -> list[dict[str, Any]]:
        """
        Run the full constitutional audit and write findings artifacts.

        Returns:
            List[dict] of findings (as_dict), consistent with prior behavior.
        """
        # REMOVED: await self.context.initialize() - Context is already initialized

        with activity_run("constitutional_audit"):
            # Discover checks first so we can construct AuditRunReporter correctly.
            check_classes = self._discover_checks()
            total_checks = len(check_classes)

            # FIXED: Create ActivityRun object instead of just a string
            run = new_activity_run("constitutional_audit")

            reporter = AuditRunReporter(
                run=run,
                repo_path=get_repo_root(),
                total_checks=total_checks,
            )

            # Reporter lifecycle is version-dependent across CORE revisions.
            # Call begin/start/open if present; otherwise no-op.
            _maybe_call(reporter, ("begin", "start", "open"))

            executed_ids: set[str] = set()
            findings, _unassigned = await self._run_all_checks(
                check_classes, reporter, executed_ids
            )

            # Call end/finish/close/finalize/complete if present; otherwise no-op.
            _maybe_call(
                reporter, ("end", "finish", "close", "finalize", "complete"), findings
            )

            findings_path = self._write_findings(findings)

            # Build or reuse symbol index if present. Many checks rely on it.
            symbol_index_path = REPORTS_DIR / SYMBOL_INDEX_FILENAME
            if not symbol_index_path.exists():
                # Keep behavior non-invasive: write an empty symbol index if missing
                symbol_index_path.write_text(json.dumps({}, indent=2), encoding="utf-8")

            processed_path = self._write_processed_findings(
                findings_path, symbol_index_path
            )

            passed = not any(f.severity == "error" for f in findings)

            evidence_path = self._write_audit_evidence(
                executed_checks=executed_ids,
                findings_path=findings_path,
                processed_findings_path=processed_path,
                passed=passed,
            )
            logger.info(
                "Wrote audit evidence: %s (%d executed checks)",
                evidence_path,
                len(executed_ids),
            )

            return [f.as_dict() for f in findings]


# Convenience entry point used by CLI layers (if any)
# ID: 20665dbf-149a-58e7-83dc-a801a2b5abfc
def test_system(root: Path | None = None) -> list[dict[str, Any]]:
    """
    Synchronous wrapper for running the full audit.

    This exists to support CLI layers that operate synchronously.
    """
    repo_root = root or get_repo_root()
    context = AuditorContext(repo_root)
    auditor = ConstitutionalAuditor(context)
    return asyncio.run(auditor.run_full_audit_async())
