# src/cli/resources/workers/remediate.py
"""
Remediation pipeline command.

Chains AuditViolationSensor → ViolationRemediator for a given audit rule.

Usage:
    # Dry-run (default) — sense violations, run LLM + Canary, post proposed
    # fixes to blackboard for review. Nothing written to src/.
    core-admin workers remediate purity.no_ast_duplication

    # Write mode — apply fixes, commit
    core-admin workers remediate purity.no_ast_duplication --write

    # Sense only — just post findings to blackboard, no LLM
    core-admin workers remediate purity.no_ast_duplication --sense-only

    # File mode — audit a single file across all rules, then remediate
    core-admin workers remediate --file src/body/workers/violation_remediator.py
    core-admin workers remediate --file src/body/workers/violation_remediator.py --write
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

from cli.utils.decorators import core_command
from shared.context import CoreContext
from shared.infrastructure.database.session_manager import get_session

from .run import workers_app


logger = logging.getLogger(__name__)
console = Console()


@workers_app.command("remediate")
@core_command(dangerous=True)
# ID: 75e79945-f796-49d5-ba87-783cae6233d0
async def remediate_cmd(
    ctx: typer.Context,
    rule: str = typer.Argument(
        None, help="Audit rule ID to remediate (e.g. 'purity.no_ast_duplication')."
    ),
    write: bool = typer.Option(
        False,
        "--write",
        help="Apply fixes to src/ and commit. Default is dry-run: LLM + Canary run but nothing is written.",
    ),
    sense_only: bool = typer.Option(
        False,
        "--sense-only",
        help="Only run the sensor — post findings to blackboard, skip LLM.",
    ),
    file: str | None = typer.Option(
        None,
        "--file",
        help=(
            "Audit a single file across all rules, then remediate. "
            "Mutually exclusive with rule and --sense-only. "
            "Path must be relative to repo root."
        ),
    ),
) -> None:
    """
    Run the autonomous remediation pipeline for a constitutional audit rule.

    Default (dry-run): sensor finds violations → LLM proposes fix →
    Canary validates → proposed fix posted to blackboard for review.

    With --write: same pipeline but fix is applied to src/ and committed.

    With --sense-only: only the sensor runs — violations are posted to
    the blackboard but no LLM is invoked.

    With --file: run a full audit scoped to a single file across all rules,
    then feed findings directly into ViolationRemediator (bypasses sensor
    and blackboard). Mutually exclusive with rule and --sense-only.

    Examples:
        # Dry-run — review proposed fixes on the blackboard first
        core-admin workers remediate purity.no_ast_duplication

        # Apply fixes
        core-admin workers remediate purity.no_ast_duplication --write

        # Just sense — populate blackboard, no LLM
        core-admin workers remediate purity.no_ast_duplication --sense-only

        # File mode — audit one file, remediate all violations found
        core-admin workers remediate --file src/body/workers/violation_remediator.py
    """
    # --- mutual exclusion checks ---
    if file and rule:
        logger.info(
            "--file and rule are mutually exclusive. "
            "Use --file to audit a single file across all rules, "
            "or provide a rule argument to use the sensor pipeline."
        )
        raise typer.Exit(code=1)

    if file and sense_only:
        logger.info(
            "--file and --sense-only are incompatible. "
            "--file already runs the audit; there is nothing to sense."
        )
        raise typer.Exit(code=1)

    if not file and not rule:
        logger.info("Either a rule argument or --file option is required.")
        raise typer.Exit(code=1)

    core_context: CoreContext = ctx.obj
    if core_context.cognitive_service is None:
        logger.error("cognitive_service not initialized")
        raise typer.Exit(1)
    async with get_session() as session:
        await core_context.cognitive_service.initialize(session)

    if file:
        await _run_file_pipeline(core_context, file, write)
    else:
        await _run_rule_pipeline(core_context, rule, write, sense_only)


async def _run_file_pipeline(
    core_context: CoreContext,
    file_path: str,
    write: bool,
) -> None:
    """Audit a single file across all rules, then run the remediation
    ceremony directly (ADR-153) — no Worker is instantiated for this path."""
    from mind.governance.audit_context import AuditorContext
    from mind.governance.auditor import ConstitutionalAuditor
    from will.remediation import NullRemediationBlackboard, RemediationCeremony

    repo_root: Path = core_context.git_service.repo_path
    abs_path = repo_root / file_path

    if not abs_path.is_file():
        logger.info("File not found: %s (resolved to %s)", file_path, abs_path)
        raise typer.Exit(code=1)

    mode = "WRITE" if write else "DRY-RUN"
    logger.info(
        "Remediation pipeline (file mode) file=%s mode=%s",
        file_path,
        mode,
    )

    # Step 1 — File-scoped full audit
    logger.info("Step 1/2 - Full audit scoped to %s", file_path)

    auditor_context: AuditorContext | None = core_context.auditor_context
    if auditor_context is None:
        logger.error("auditor_context not initialized")
        return
    async with get_session() as session:
        auditor_context.db_session = session
        await auditor_context.load_knowledge_graph()
        auditor = ConstitutionalAuditor(auditor_context)
        result = await auditor.run_full_audit_async()
        auditor_context.db_session = None

    all_findings = result.get("findings", [])
    file_findings = _filter_findings_for_file(all_findings, file_path)

    if not file_findings:
        logger.info("No violations found in %s", file_path)
        return

    logger.info(
        "Found %d violation(s) in %s across %d rule(s)",
        len(file_findings),
        file_path,
        len({f["rule"] for f in file_findings}),
    )

    # Step 2 — Run the remediation ceremony directly.
    logger.info("Step 2/2 - RemediationCeremony (file mode)")

    # Build synthetic blackboard-style finding dicts RemediationCeremony expects.
    synthetic_findings = _build_synthetic_findings(file_findings, file_path)

    # Determine a combined target_rule label for the ceremony.
    unique_rules = sorted({f["rule"] for f in file_findings})
    target_rule = unique_rules[0] if len(unique_rules) == 1 else "file-audit"

    # ADR-153: no blackboard entries exist for this ad-hoc, single-file
    # audit — NullRemediationBlackboard makes that explicit and typed,
    # replacing the old pattern of instantiating ViolationRemediator (a
    # Worker) and monkeypatching its claim/mark methods to bypass the
    # blackboard. This is a deliberate, recorded behavior change (ADR-153
    # D2/Consequences): unlike before, this path now posts nothing to the
    # blackboard at all — no worker.heartbeat, no dry_run_complete
    # observation. Console output below (unchanged) is the only feedback.
    ceremony = RemediationCeremony(
        core_context=core_context,
        target_rule=target_rule,
        write=write,
        blackboard=NullRemediationBlackboard(),
    )
    await ceremony.process_file(file_path, synthetic_findings)
    logger.info("Remediation complete.")

    console.print()
    if write:
        logger.info(
            "Pipeline complete in WRITE mode. "
            "Fixes applied and committed. Run audit to verify:"
        )
        logger.info("  core-admin code audit")
    else:
        logger.info(
            "Pipeline complete in DRY-RUN mode. "
            "Proposed fixes are on the blackboard. Review them:"
        )
        logger.info(
            "  core-admin workers blackboard --filter 'audit.remediation.dry_run'"
        )
        logger.info("\nWhen satisfied, apply with:")
        logger.info("  core-admin workers remediate --file %s --write", file_path)


def _filter_findings_for_file(
    findings: list[Any], target_file: str
) -> list[dict[str, Any]]:
    """Filter audit findings to only those matching the target file path."""
    result = []
    for f in findings:
        if isinstance(f, dict):
            fp = f.get("file_path") or ""
            check_id = f.get("check_id", "unknown")
            message = f.get("message", "")
            severity = str(f.get("severity", "warning"))
            line_number = f.get("line_number")
        else:
            fp = getattr(f, "file_path", None) or ""
            check_id = getattr(f, "check_id", "unknown")
            message = getattr(f, "message", "")
            severity = str(getattr(f, "severity", "warning"))
            line_number = getattr(f, "line_number", None)

        if fp == target_file:
            result.append(
                {
                    "file_path": fp,
                    "rule": check_id,
                    "message": message,
                    "severity": severity,
                    "line_number": line_number,
                }
            )
    return result


def _build_synthetic_findings(
    file_findings: list[dict[str, Any]], file_path: str
) -> list[dict[str, Any]]:
    """Convert filtered audit findings into the blackboard-entry format RemediationCeremony expects."""
    synthetic = []
    for f in file_findings:
        synthetic.append(
            {
                "id": str(uuid.uuid4()),
                "payload": {
                    "file_path": file_path,
                    "rule": f["rule"],
                    "message": f["message"],
                    "severity": f["severity"],
                    "line_number": f.get("line_number"),
                    "status": "unprocessed",
                },
            }
        )
    return synthetic


async def _run_rule_pipeline(
    core_context: CoreContext,
    rule: str,
    write: bool,
    sense_only: bool,
) -> None:
    """Original rule-based pipeline: AuditViolationSensor → ViolationRemediator."""
    from will.workers.audit_violation_sensor import AuditViolationSensor
    from will.workers.violation_remediator_body import ViolationRemediator

    mode = "SENSE-ONLY" if sense_only else "WRITE" if write else "DRY-RUN"
    logger.info(
        "Remediation pipeline rule=%s mode=%s",
        rule,
        mode,
    )
    logger.info("Step 1/2 - AuditViolationSensor")
    sensor = AuditViolationSensor(
        core_context=core_context,
        declaration_name=f"audit_sensor_{rule.split('.')[0]}",
        rule_namespace=rule,
        dry_run=not write,
    )
    await sensor.start()
    logger.info("Sensor complete.")
    if sense_only:
        logger.info("--sense-only: skipping remediator. Check blackboard for findings:")
        logger.info("  core-admin workers blackboard --filter 'python::%s'", rule)
        return
    logger.info("Step 2/2 - ViolationRemediator")
    remediator = ViolationRemediator(
        core_context=core_context, target_rule=rule, write=write
    )
    await remediator.start()
    logger.info("Remediator complete.")
    console.print()
    if write:
        logger.info(
            "Pipeline complete in WRITE mode. "
            "Fixes applied and committed. Run audit to verify:"
        )
        logger.info("  core-admin code audit")
    else:
        logger.info(
            "Pipeline complete in DRY-RUN mode. "
            "Proposed fixes are on the blackboard. Review them:"
        )
        logger.info(
            "  core-admin workers blackboard --filter 'audit.remediation.dry_run'"
        )
        logger.info("\nWhen satisfied, apply with:")
        logger.info("  core-admin workers remediate %s --write", rule)
