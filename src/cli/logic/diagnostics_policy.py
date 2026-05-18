# src/cli/logic/diagnostics_policy.py

"""
Logic for constitutional policy coverage auditing.

Thin client over POST /v1/quality/policy-coverage. The audit runs
server-side via mind.governance.PolicyCoverageService; this module
calls the endpoint and owns rendering only.
"""

from __future__ import annotations

import logging
from typing import Any

import typer

from api.cli import CoreApiClient


logger = logging.getLogger(__name__)


def _log_policy_coverage_summary(summary: dict[str, Any]) -> None:
    """Log a compact summary of policy coverage metrics."""
    logger.info("Constitutional Policy Coverage Summary")
    logger.info("Policies Seen: %s", summary.get("policies_seen", 0))
    logger.info("Rules Found: %s", summary.get("rules_found", 0))
    logger.info("Rules (direct): %s", summary.get("rules_direct", 0))
    logger.info("Rules (bound): %s", summary.get("rules_bound", 0))
    logger.info("Rules (inferred): %s", summary.get("rules_inferred", 0))
    logger.info("Uncovered Rules (all): %s", summary.get("uncovered_rules", 0))
    logger.info("Uncovered ERROR Rules: %s", summary.get("uncovered_error_rules", 0))


def _log_policy_coverage_table(records: list[dict[str, Any]]) -> None:
    """Log all rules with their coverage type so gaps are visible."""
    if not records:
        logger.warning("No policy rules discovered; nothing to display.")
        return
    logger.info("Policy Rules Coverage")
    sorted_records = sorted(
        records,
        key=lambda r: (
            not r.get("covered", False),
            r.get("policy_id", ""),
            r.get("rule_id", ""),
        ),
    )
    for rec in sorted_records:
        logger.info(
            "Policy: %s, Rule ID: %s, Enforcement: %s, Coverage: %s, Covered?: %s",
            rec.get("policy_id", ""),
            rec.get("rule_id", ""),
            rec.get("enforcement", ""),
            rec.get("coverage", "none"),
            "Yes" if rec.get("covered", False) else "No",
        )


def _log_uncovered_policy_rules(records: list[dict[str, Any]]) -> None:
    """Only log the rules that are not covered."""
    uncovered = [r for r in records if not r.get("covered", False)]
    if not uncovered:
        return
    logger.warning("Uncovered Policy Rules")
    for rec in uncovered:
        logger.warning(
            "Policy: %s, Rule ID: %s, Enforcement: %s, Coverage: %s",
            rec.get("policy_id", ""),
            rec.get("rule_id", ""),
            rec.get("enforcement", ""),
            rec.get("coverage", "none"),
        )


# ID: 6eb5c3ca-cbbf-48d1-82a5-de01df839b6f
async def policy_coverage() -> None:
    """
    Runs a meta-audit on all .intent/policies/ to ensure they are
    well-formed and covered by the governance model.

    Thin client over POST /v1/quality/policy-coverage; this function
    fetches the report and renders it via the local _log_* helpers.
    """
    logger.info("Running Constitutional Policy Coverage Audit...")
    client = CoreApiClient()
    report = await client.quality_policy_coverage()
    logger.info("Report ID: %s", report.get("report_id", ""))
    summary = report.get("summary", {})
    records = report.get("records", [])
    _log_policy_coverage_summary(summary)
    _log_policy_coverage_table(records)
    if summary.get("uncovered_rules", 0) > 0:
        _log_uncovered_policy_rules(records)
    exit_code = report.get("exit_code", 0)
    if exit_code != 0:
        logger.error("Policy coverage audit failed with exit code: %s", exit_code)
        raise typer.Exit(code=exit_code)
    logger.info("All active policies are backed by implemented or inferred checks.")
