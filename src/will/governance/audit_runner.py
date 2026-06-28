# src/will/governance/audit_runner.py

"""
Audit runner facade — Will-layer entry point for the /audit API
(ADR-054 D1).

The API layer must not import mind.* or shared.infrastructure.* by
constitutional rule. This module is the sanctioned bridge: it wraps the
auditor and the post-processing chain and exposes async functions the
API can call with an injected session.

Two entry points:

* `run_and_persist_audit` — fire-and-forget path used by the async
  POST /audit/runs (status 202). Inserts a pending row, runs the
  workflow, updates the row with the final verdict and counts. Does
  not return findings.

* `run_sync_audit` — synchronous path used by POST /audit/runs with
  `wait=true` (status 200). Runs the full ConstitutionalAuditor or
  the filtered_audit branch, applies the entry-point downgrade,
  writes the report files (findings.json, auto-ignored MD/JSON,
  evidence ledger) for full audits, INSERTs a completed audit_runs
  row, and returns the full result dict the CLI needs to render.

Persistence target is core.audit_runs (the canonical audit-run
table; see migration 20260518_consolidate_audit_runs.sql which folded
the short-lived audit_run_resources sibling back into it).
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import text

from body.services.file_service import FileService
from mind.enforcement.audit import run_audit_workflow
from mind.governance.audit_postprocessor import apply_entry_point_downgrade
from mind.governance.audit_report_writer import build_auto_ignored_markdown
from mind.governance.auditor import AuditVerdict, ConstitutionalAuditor
from mind.governance.filtered_audit import run_filtered_audit
from shared.context import CoreContext
from shared.logger import getLogger
from shared.path_resolver import PathResolver
from shared.workers.blackboard_publisher import _sanitize_payload


__all__ = [
    "AuditVerdict",
    "ConstitutionalAuditor",
    "run_and_persist_audit",
    "run_sync_audit",
]


logger = getLogger(__name__)


_BLOCKING_SEVERITIES = {"error", "critical"}


def _blocking_count_from_dicts(findings: list[dict]) -> int:
    return sum(
        1
        for f in findings
        if str(f.get("severity", "")).lower() in _BLOCKING_SEVERITIES
    )


# ID: 045484b6-7e52-46df-b4b6-53f3e7a0de65
async def run_and_persist_audit(
    context: CoreContext,
    session: Any,
    run_id: UUID | None = None,
) -> dict:
    """Run the constitutional audit and persist the result.

    When `run_id` is None, a fresh row is INSERTed (status='pending'
    placeholder is written and overwritten with the final verdict in
    the same call). When `run_id` is supplied, the existing row — the
    pending row the API route pre-inserted so it could return the id
    to the caller with 202 — is UPDATEd in place.

    Returns:
        dict with run_id (str), verdict, finding_count, blocking_count,
        status. The shape is what /audit/runs and /audit/runs/{id}
        callers expect.
    """
    if run_id is None:
        result = await session.execute(
            text(
                """
                INSERT INTO core.audit_runs
                    (source, verdict, finding_count, blocking_count, status)
                VALUES ('api', 'pending', 0, 0, 'pending')
                RETURNING run_id
                """
            )
        )
        run_id = result.scalar_one()
        await session.commit()
        logger.info("audit_runner: inserted pending run %s", run_id)

    try:
        passed, findings = await run_audit_workflow(context)
    except Exception:
        logger.exception("audit_runner: run_audit_workflow raised for %s", run_id)
        await session.execute(
            text(
                """
                UPDATE core.audit_runs
                   SET status = 'failed',
                       finished_at = now()
                 WHERE run_id = :rid
                """
            ),
            {"rid": run_id},
        )
        await session.commit()
        raise

    verdict = AuditVerdict.PASS if passed else AuditVerdict.FAIL
    finding_count = len(findings)
    blocking_count = sum(1 for f in findings if f.severity.is_blocking)
    findings_dicts = [f.as_dict() if hasattr(f, "as_dict") else f for f in findings]

    await session.execute(
        text(
            """
            UPDATE core.audit_runs
               SET verdict = :verdict,
                   finding_count = :finding_count,
                   blocking_count = :blocking_count,
                   findings = cast(:findings as jsonb),
                   status = 'completed',
                   finished_at = now()
             WHERE run_id = :rid
            """
        ),
        {
            "verdict": verdict.value,
            "finding_count": finding_count,
            "blocking_count": blocking_count,
            # ASCII-sanitize the findings payload before JSONB bind — the
            # core DB is SQL_ASCII; raw Unicode escapes (e.g. U+0000 in
            # an audit-finding message) trigger asyncpg's
            # UntranslatableCharacterError on INSERT. Mirrors the
            # blackboard payload pattern (see shared.workers.base) — #359.
            "findings": json.dumps(_sanitize_payload(findings_dicts)),
            "rid": run_id,
        },
    )
    await session.commit()

    logger.info(
        "audit_runner: %s completed verdict=%s findings=%d blocking=%d",
        run_id,
        verdict.value,
        finding_count,
        blocking_count,
    )

    return {
        "run_id": str(run_id),
        "verdict": verdict.value,
        "finding_count": finding_count,
        "blocking_count": blocking_count,
        "status": "completed",
    }


# ID: 0756d794-1c08-4eba-93f4-27bb066b0a15
async def run_sync_audit(
    context: CoreContext,
    session: Any,
    *,
    rule_ids: list[str] | None = None,
    policy_ids: list[str] | None = None,
    files: list[str] | None = None,
    force_llm: bool = False,
    source: str = "api",
) -> dict:
    """Run the audit synchronously and return the full result.

    Backs `POST /v1/audit/runs` with `wait=true`. Mirrors what the
    legacy `core-admin code audit` CLI used to do client-side:

    * Filtered runs (any of rule_ids / policy_ids / files set) call
      `run_filtered_audit` over the supplied scope. No persistence,
      no report files — same as the legacy CLI.
    * Full runs call `ConstitutionalAuditor.run_full_audit_async()`,
      apply the entry-point downgrade, INSERT a completed
      `core.audit_runs` row, and write the report-file set
      (findings.json, auto_ignored.{md,json}, evidence ledger).

    Daemon coexistence: this sets `context.auditor_context.db_session`
    and `force_llm` directly, matching the legacy CLI pattern. The
    daemon's AuditViolationSensor uses the same shared context, so a
    long-running sync API call overlapping a sensor cycle could race
    on those attributes. The race window matches the legacy CLI's
    (audits were always concurrent with the daemon when invoked from
    the operator's shell); accepted as inherited risk, not addressed
    in this change.
    """
    rule_ids = list(rule_ids or [])
    policy_ids = list(policy_ids or [])
    files = list(files or [])
    filtered = bool(rule_ids or policy_ids or files)

    context.auditor_context.db_session = session
    context.auditor_context.force_llm = force_llm

    start_time = time.perf_counter()
    try:
        if filtered:
            await context.auditor_context.load_knowledge_graph()
            raw_findings, executed_ids, stats_dict = await run_filtered_audit(
                context.auditor_context,
                rule_ids=rule_ids,
                policy_ids=policy_ids,
                files=files or None,
            )
            results: dict[str, Any] = {
                "findings": raw_findings,
                "executed_rule_ids": executed_ids,
                "passed": True,
                "stats": stats_dict,
                "verdict": None,
            }
        else:
            auditor = ConstitutionalAuditor(context.auditor_context)
            results = await auditor.run_full_audit_async()
    finally:
        context.auditor_context.db_session = None

    duration = time.perf_counter() - start_time

    findings_raw = results["findings"]
    findings_dicts = [f.as_dict() if hasattr(f, "as_dict") else f for f in findings_raw]
    processed_findings, ignored_data = apply_entry_point_downgrade(
        findings=findings_dicts, symbol_index={}
    )

    verdict_enum = results.get("verdict")
    verdict_str = (
        verdict_enum.value
        if verdict_enum is not None
        else ("PASS" if results["passed"] else "FAIL")
    )

    common_payload: dict[str, Any] = {
        "verdict": verdict_str,
        "passed": results["passed"],
        "stats": results.get("stats", {}),
        "findings": processed_findings,
        "executed_rule_ids": sorted(list(results.get("executed_rule_ids", []))),
        "auto_ignored": ignored_data,
        "duration_sec": duration,
    }

    if filtered:
        common_payload["run_id"] = None
        return common_payload

    finished_at = datetime.now(UTC)
    started_at = finished_at - timedelta(seconds=duration)
    try:
        sha = context.git_service.get_current_commit()[:40]
    except Exception:
        sha = ""

    finding_count = len(processed_findings)
    blocking_count = _blocking_count_from_dicts(processed_findings)

    insert_result = await session.execute(
        text(
            """
            INSERT INTO core.audit_runs (
                source, commit_sha, verdict, status,
                finding_count, blocking_count,
                findings,
                started_at, finished_at
            ) VALUES (
                :source, :sha, :verdict, 'completed',
                :finding_count, :blocking_count,
                cast(:findings as jsonb),
                :started_at, :finished_at
            )
            RETURNING run_id
            """
        ),
        {
            "source": source,
            "sha": sha,
            "verdict": verdict_str,
            "finding_count": finding_count,
            "blocking_count": blocking_count,
            # ASCII-sanitize the findings payload before JSONB bind — the
            # core DB is SQL_ASCII; raw Unicode escapes (e.g. U+0000 in
            # an audit-finding message) trigger asyncpg's
            # UntranslatableCharacterError on INSERT. Mirrors the
            # blackboard payload pattern (see shared.workers.base) — #359.
            "findings": json.dumps(_sanitize_payload(processed_findings)),
            "started_at": started_at,
            "finished_at": finished_at,
        },
    )
    run_id = insert_result.scalar_one()
    await session.commit()

    repo_root = context.git_service.repo_path
    path_resolver = PathResolver.from_repo(repo_root)
    file_service = FileService(repo_root)

    findings_file = str(
        (path_resolver.reports_dir / "audit_findings.json").relative_to(repo_root)
    )
    evidence_file = str(
        (path_resolver.reports_dir / "audit" / "latest_audit.json").relative_to(
            repo_root
        )
    )
    ignored_md = str(
        (path_resolver.reports_dir / "audit_auto_ignored.md").relative_to(repo_root)
    )
    ignored_json = str(
        (path_resolver.reports_dir / "audit_auto_ignored.json").relative_to(repo_root)
    )
    audit_subdir = str((path_resolver.reports_dir / "audit").relative_to(repo_root))
    file_service.ensure_dir(audit_subdir)

    timestamp_str = finished_at.strftime("%Y-%m-%dT%H:%M:%SZ")

    file_service.write(findings_file, json.dumps(processed_findings, indent=2))
    file_service.write(
        ignored_md, build_auto_ignored_markdown(timestamp_str, ignored_data)
    )
    file_service.write_json(
        ignored_json, {"generated_at": timestamp_str, "items": ignored_data}
    )

    evidence = {
        "audit_id": str(run_id),
        "timestamp": timestamp_str,
        "passed": results["passed"],
        "findings_count": finding_count,
        "executed_rules": common_payload["executed_rule_ids"],
        "verdict": verdict_str,
    }
    file_service.write(evidence_file, json.dumps(evidence, indent=2))

    logger.info(
        "audit_runner: sync %s completed verdict=%s findings=%d blocking=%d "
        "duration=%.2fs",
        run_id,
        verdict_str,
        finding_count,
        blocking_count,
        duration,
    )

    common_payload["run_id"] = str(run_id)
    return common_payload
