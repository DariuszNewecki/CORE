# src/body/cli/logic/diagnostics_policy.py

"""
Logic for constitutional policy coverage auditing.
"""

from __future__ import annotations

from shared.logger import getLogger


logger = getLogger(__name__)
import logging
from pathlib import Path
from typing import Any

import typer

from mind.governance.policy_coverage_service import PolicyCoverageService
from shared.path_resolver import PathResolver


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
        policy = rec.get("policy_id", "")
        rule_id = rec.get("rule_id", "")
        enforcement = rec.get("enforcement", "")
        coverage = rec.get("coverage", "none")
        covered = rec.get("covered", False)
        covered_str = "Yes" if covered else "No"
        logger.info(
            "Policy: %s, Rule ID: %s, Enforcement: %s, Coverage: %s, Covered?: %s",
            policy,
            rule_id,
            enforcement,
            coverage,
            covered_str,
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
def policy_coverage():
    """
    Runs a meta-audit on all .intent/charter/policies/ to ensure they are
    well-formed and covered by the governance model.
    """
    logger.info("Running Constitutional Policy Coverage Audit...")
    path_resolver = PathResolver.from_repo(
        repo_root=Path.cwd(), intent_root=Path.cwd() / ".intent"
    )
    service = PolicyCoverageService(path_resolver)
    report = service.run()
    logger.info("Report ID: %s", report.report_id)
    _log_policy_coverage_summary(report.summary)
    _log_policy_coverage_table(report.records)
    if report.summary.get("uncovered_rules", 0) > 0:
        _log_uncovered_policy_rules(report.records)
    if report.exit_code != 0:
        logger.error(
            "Policy coverage audit failed with exit code: %s", report.exit_code
        )
        raise typer.Exit(code=report.exit_code)
    logger.info("All active policies are backed by implemented or inferred checks.")
