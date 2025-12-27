# src/body/cli/commands/check/rule.py
"""
Filtered/focused audit command.

Run specific rules or policies for targeted remediation.
Enables focused work on one problem at a time.
"""

from __future__ import annotations

import typer
from rich.console import Console

from body.cli.commands.check.converters import (
    convert_finding_dicts_to_models,
    parse_min_severity,
)
from body.cli.commands.check.formatters import (
    print_executed_rules,
    print_filtered_audit_summary,
    print_summary_findings,
    print_verbose_findings,
)
from mind.governance.filtered_audit import run_filtered_audit
from shared.cli_utils import core_command
from shared.context import CoreContext
from shared.models import AuditSeverity


console = Console()


# ID: d5e6f7a8-9b0c-1d2e-3f4a-5b6c7d8e9f0a
@core_command(dangerous=False)
# ID: 2abc4cf1-e9ba-48ea-a6f7-f26842563bc4
async def rule_cmd(
    ctx: typer.Context,
    rule: list[str] = typer.Option(
        [],
        "--rule",
        "-r",
        help="Specific rule ID(s) to execute (can be repeated)",
    ),
    policy: list[str] = typer.Option(
        [],
        "--policy",
        "-p",
        help="Execute all rules from specific policy ID(s) (can be repeated)",
    ),
    pattern: list[str] = typer.Option(
        [],
        "--pattern",
        help="Regex pattern(s) for rule IDs (can be repeated)",
    ),
    severity: str = typer.Option(
        "warning",
        "--severity",
        "-s",
        help="Filter findings by minimum severity level (info, warning, error).",
        case_sensitive=False,
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show all individual findings instead of a summary.",
    ),
) -> None:
    """
    Run constitutional audit for specific rules or policies.

    Examples:
      # Run single rule
      core-admin check rule --rule linkage.capability.unassigned

      # Run all rules from a policy
      core-admin check rule --policy standard_code_linkage

      # Run multiple rules
      core-admin check rule -r linkage.assign_ids -r linkage.duplicate_ids

      # Run rules matching pattern
      core-admin check rule --pattern "linkage.*"

      # Combine filters
      core-admin check rule --policy code.capabilities --rule linkage.assign_ids
    """
    core_context: CoreContext = ctx.obj

    # Validate at least one filter specified
    if not rule and not policy and not pattern:
        console.print(
            "[red]Error: Must specify at least one filter:[/red]\n"
            "  --rule <rule_id>\n"
            "  --policy <policy_id>\n"
            "  --pattern <regex>\n"
        )
        console.print("\nUse --help for examples")
        raise typer.Exit(1)

    # Load knowledge graph
    await core_context.auditor_context.load_knowledge_graph()

    # Execute filtered audit
    console.print("[bold cyan]🔍 Running Filtered Constitutional Audit[/bold cyan]\n")

    if rule:
        console.print(f"  Rules: {', '.join(rule)}")
    if policy:
        console.print(f"  Policies: {', '.join(policy)}")
    if pattern:
        console.print(f"  Patterns: {', '.join(pattern)}")
    console.print()

    executed_rule_ids: set[str] = set()

    findings_dicts, executed_rules, stats = await run_filtered_audit(
        core_context.auditor_context,
        rule_ids=rule or None,
        policy_ids=policy or None,
        rule_patterns=pattern or None,
        executed_rule_ids=executed_rule_ids,
    )

    # Convert findings dicts to models
    all_findings = convert_finding_dicts_to_models(findings_dicts)

    # Filter by severity
    min_severity = parse_min_severity(severity)
    filtered_findings = [f for f in all_findings if f.severity >= min_severity]

    # Display results
    errors = [f for f in all_findings if f.severity.is_blocking]
    warnings = [f for f in all_findings if f.severity == AuditSeverity.WARNING]

    passed = len(errors) == 0

    print_filtered_audit_summary(
        passed=passed,
        stats=stats,
        errors=errors,
        warnings=warnings,
    )

    if filtered_findings:
        if verbose:
            print_verbose_findings(filtered_findings)
        else:
            print_summary_findings(filtered_findings)

    # Show which rules were executed
    if executed_rules and not verbose:
        print_executed_rules(executed_rules)

    if not passed:
        raise typer.Exit(1)
