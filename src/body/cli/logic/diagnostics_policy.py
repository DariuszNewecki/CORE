# src/body/cli/logic/diagnostics_policy.py
"""
Logic for constitutional policy coverage auditing.
"""

from __future__ import annotations

import logging
from typing import Any

import typer

from mind.governance.policy_coverage_service import PolicyCoverageService


logger = logging.getLogger(__name__)


def _log_policy_coverage_summary(summary: dict[str, Any]) -> None:
    """Log a compact summary of policy coverage metrics."""
    logger.info("Constitutional Policy Coverage Summary")
    logger.info(f"Policies Seen: {summary.get('policies_seen', 0)}")
    logger.info(f"Rules Found: {summary.get('rules_found', 0)}")
    logger.info(f"Rules (direct): {summary.get('rules_direct', 0)}")
    logger.info(f"Rules (bound): {summary.get('rules_bound', 0)}")
    logger.info(f"Rules (inferred): {summary.get('rules_inferred', 0)}")
    logger.info(f"Uncovered Rules (all): {summary.get('uncovered_rules', 0)}")
    logger.info(f"Uncovered ERROR Rules: {summary.get('uncovered_error_rules', 0)}")


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
        policy = rec.get("policy_id", "")
        rule_id = rec.get("rule_id", "")
        enforcement = rec.get("enforcement", "")
        coverage = rec.get("coverage", "none")
        covered = rec.get("covered", False)
        covered_str = "Yes" if covered else "No"
        logger.info(
            f"Policy: {policy}, Rule ID: {rule_id}, Enforcement: {enforcement}, "
            f"Coverage: {coverage}, Covered?: {covered_str}"
        )


def _log_uncovered_policy_rules(records: list[dict[str, Any]]) -> None:
    """Only log the rules that are not covered."""
    uncovered = [r for r in records if not r.get("covered", False)]
    if not uncovered:
        return

    logger.warning("Uncovered Policy Rules")
    for rec in uncovered:
        logger.warning(
            f"Policy: {rec.get('policy_id', '')}, "
            f"Rule ID: {rec.get('rule_id', '')}, "
            f"Enforcement: {rec.get('enforcement', '')}, "
            f"Coverage: {rec.get('coverage', 'none')}"
        )


# ID: 25d4e8f9-ae1e-424e-972d-2dcb74f918b7
def policy_coverage():
    """
    Runs a meta-audit on all .intent/charter/policies/ to ensure they are
    well-formed and covered by the governance model.
    """
    logger.info("Running Constitutional Policy Coverage Audit...")
    service = PolicyCoverageService()
    report = service.run()

    logger.info(f"Report ID: {report.report_id}")

    _log_policy_coverage_summary(report.summary)
    _log_policy_coverage_table(report.records)

    if report.summary.get("uncovered_rules", 0) > 0:
        _log_uncovered_policy_rules(report.records)

    if report.exit_code != 0:
        logger.error(f"Policy coverage audit failed with exit code: {report.exit_code}")
        raise typer.Exit(code=report.exit_code)

    logger.info("All active policies are backed by implemented or inferred checks.")
