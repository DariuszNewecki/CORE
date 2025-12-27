# src/mind/governance/auditor.py
"""
Constitutional Auditor - The primary orchestration engine for all governance checks.

Discovers and runs all registered audit checks, coordinating their findings into
a single, comprehensive report. Emits evidence artifacts for downstream tools.

Key outputs (legacy, unchanged):
- reports/audit_findings.json
- reports/audit_findings.processed.json

Authoritative evidence artifact:
- reports/audit/latest_audit.json
  Contains executed_rules for *all* policy rules that were attempted via checks,
  even if they produced zero findings. executed_checks remains for diagnostics.

FIX (minimal, safe):
- Track governance coverage by rule IDs AND track diagnostics by check IDs.
- Always add policy_rule_ids for a check, even when metadata.id exists.
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

from body.cli.commands.audit_reporter import AuditRunReporter
from mind.governance import checks
from mind.governance.audit_context import AuditorContext
from mind.governance.audit_postprocessor import (
    EntryPointAllowList,
    apply_entry_point_downgrade_and_report,
)
from mind.governance.audit_types import AuditCheckMetadata, AuditCheckResult
from mind.governance.checks.base_check import BaseCheck
from mind.governance.constitutional_auditor_dynamic import (
    get_dynamic_execution_stats,
    run_dynamic_rules,
)
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

# Evidence artifact path
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


async def _normalize_findings(result: Any) -> list[AuditFinding]:
    """
    Normalize a check's execute() return value to List[AuditFinding].

    Handles:
    - sync returning list[AuditFinding]
    - async returning list[AuditFinding]
    - sync returning an awaitable (coroutine) that yields list[AuditFinding]
    """
    if inspect.isawaitable(result):
        result = await result

    if result is None:
        return []

    if isinstance(result, list):
        return result

    if isinstance(result, (tuple, set)):
        return list(result)

    try:
        return list(result)  # type: ignore[arg-type]
    except Exception as e:
        raise TypeError(
            f"Check returned unsupported findings type: {type(result)!r}"
        ) from e


def _extract_policy_rule_ids(check_cls: type[BaseCheck]) -> list[str]:
    """
    Extract policy rule IDs declared by a check.

    Convention:
      class MyCheck(BaseCheck):
          policy_rule_ids = ["rule.a", "rule.b"]
    """
    rule_ids = getattr(check_cls, "policy_rule_ids", None)
    if not isinstance(rule_ids, list):
        return []
    out: list[str] = []
    for rid in rule_ids:
        if isinstance(rid, str) and rid.strip():
            out.append(rid.strip())
    return out


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
        *,
        executed_rule_ids: set[str],
        executed_check_ids: set[str],
    ) -> tuple[list[AuditFinding], int]:
        """
        Instantiates and runs all discovered checks, collecting their findings.

        executed_check_ids:
          - diagnostic identity of executed checks (metadata.id preferred, else class name)

        executed_rule_ids:
          - policy rule IDs enforced/attempted by executed checks (policy_rule_ids)
          - plus any finding.check_id observed during execution (legacy compatibility)
        """
        all_findings: list[AuditFinding] = []

        # Lazy service placeholder (checks requiring services should handle None or use registry)
        qdrant_service = None

        for check_class in check_classes:
            # 1) Diagnostics: check identity
            meta_id = _check_metadata_id(check_class)
            executed_check_ids.add(meta_id or check_class.__name__)

            # 2) Coverage: ALWAYS include policy_rule_ids (even if meta_id exists)
            for rid in _extract_policy_rule_ids(check_class):
                executed_rule_ids.add(rid)

            start = time.perf_counter()
            try:
                try:
                    check_instance: BaseCheck = check_class(self.context)  # type: ignore[call-arg]
                except TypeError:
                    check_instance = check_class(self.context, qdrant_service)  # type: ignore[call-arg]

                # Execute (support: async execute, sync execute, sync returning awaitable)
                if inspect.iscoroutinefunction(check_instance.execute):
                    raw = await check_instance.execute()
                else:
                    raw = await asyncio.to_thread(check_instance.execute)

                findings = await _normalize_findings(raw)

                # Legacy compatibility: if findings carry check_id, count them as executed rules
                for f in findings:
                    if isinstance(f.check_id, str) and f.check_id.strip():
                        executed_rule_ids.add(f.check_id.strip())

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
            dead_rule_ids=tuple(),  # No longer downgrading any rules
            downgrade_to=DOWNGRADE_SEVERITY_TO,
            write_reports=True,
        )
        out_path.write_text(json.dumps(processed, indent=2), encoding="utf-8")
        return out_path

    def _write_audit_evidence(
        self,
        *,
        executed_rules: set[str],
        executed_checks: set[str],
        findings_path: Path,
        processed_findings_path: Path,
        passed: bool,
    ) -> Path:
        evidence_path = AUDIT_EVIDENCE_DIR / AUDIT_EVIDENCE_FILENAME

        payload: dict[str, Any] = {
            "schema_version": "0.2.0",
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
            # Authoritative for governance coverage
            "executed_rules": sorted(executed_rules),
            # Diagnostic / legacy visibility
            "executed_checks": sorted(executed_checks),
        }

        _safe_write_json(evidence_path, payload)
        return evidence_path

    # ID: 178b5c18-373c-4d39-be91-9c71f37f4a23
    async def run_full_audit_async(self) -> list[dict[str, Any]]:
        await self.context.load_knowledge_graph()

        with activity_run("constitutional_audit"):
            check_classes = self._discover_checks()
            total_checks = len(check_classes)

            run = new_activity_run("constitutional_audit")

            reporter = AuditRunReporter(
                run=run,
                repo_path=get_repo_root(),
                total_checks=total_checks,
            )

            _maybe_call(reporter, ("begin", "start", "open"))

            executed_rule_ids: set[str] = set()
            executed_check_ids: set[str] = set()

            # PHASE 1 POC: Run dynamic rules BEFORE legacy checks
            logger.info("=== Running Dynamic Rule Execution (POC) ===")
            dynamic_findings = await run_dynamic_rules(
                self.context, executed_rule_ids=executed_rule_ids
            )
            logger.info("Dynamic rules produced %d findings", len(dynamic_findings))

            # Run legacy Check classes (backward compatibility)
            logger.info("=== Running Legacy Check Classes ===")
            findings, _unassigned = await self._run_all_checks(
                check_classes,
                reporter,
                executed_rule_ids=executed_rule_ids,
                executed_check_ids=executed_check_ids,
            )
            logger.info("Legacy checks produced %d findings", len(findings))

            # Merge findings
            findings = dynamic_findings + findings
            logger.info("Total findings: %d", len(findings))

            _maybe_call(
                reporter, ("end", "finish", "close", "finalize", "complete"), findings
            )

            findings_path = self._write_findings(findings)

            symbol_index_path = REPORTS_DIR / SYMBOL_INDEX_FILENAME
            if not symbol_index_path.exists():
                symbol_index_path.write_text(json.dumps({}, indent=2), encoding="utf-8")

            processed_path = self._write_processed_findings(
                findings_path, symbol_index_path
            )

            passed = not any(f.severity == "error" for f in findings)

            # Log dynamic execution statistics
            stats = get_dynamic_execution_stats(self.context, executed_rule_ids)
            logger.info("Dynamic Execution Stats: %s", stats)

            evidence_path = self._write_audit_evidence(
                executed_rules=executed_rule_ids,
                executed_checks=executed_check_ids,
                findings_path=findings_path,
                processed_findings_path=processed_path,
                passed=passed,
            )
            logger.info(
                "Wrote audit evidence: %s (%d executed rules, %d executed checks)",
                evidence_path,
                len(executed_rule_ids),
                len(executed_check_ids),
            )

            return [f.as_dict() for f in findings]


# Convenience entry point used by CLI layers (if any)
# ID: 20665dbf-149a-58e7-83dc-a801a2b5abfc
async def test_system(root: Path | None = None) -> list[dict[str, Any]]:
    repo_root = root or get_repo_root()
    context = AuditorContext(repo_root)
    auditor = ConstitutionalAuditor(context)
    return await auditor.run_full_audit_async()
