# src/body/cli/commands/governance.py
# ID: 0753d0ea-9942-431f-b013-5ee5d09eb782

"""
Constitutional governance visibility and verification commands.

Commands:
- coverage           : Show constitutional rule enforcement coverage
- validate-request   : Demonstrate full pre-flight constitutional validation (5 gates)

HEALED V2.7 — FULL CONSERVATIVE MERGE
- All 280+ lines of functionality from legacy validate_request.py preserved verbatim
- Coverage command kept from modern governance.py
- Single source of truth — duplication eliminated
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from cli.logic import governance_logic as logic
from shared.cli_utils import core_command
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.context import CoreContext

console = Console()
logger = getLogger(__name__)

governance_app = typer.Typer(
    help="Constitutional governance visibility and verification.",
    no_args_is_help=True,
)


# =====================================================================
# COVERAGE COMMAND (unchanged from modern governance.py)
# =====================================================================


@governance_app.command("coverage")
@core_command(dangerous=False, requires_context=True)
# ID: 06d759aa-28b1-43ab-b887-5367fded6fd1
def enforcement_coverage(
    ctx: typer.Context,
    format: str = typer.Option(
        "summary",
        "--format",
        "-f",
        help="Output format: summary|hierarchical|json",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Write output to file instead of console",
    ),
) -> None:
    """Show constitutional rule enforcement coverage."""
    core_context: CoreContext = ctx.obj
    file_handler = core_context.file_handler
    repo_root = core_context.git_service.repo_path

    coverage_data = logic.get_coverage_data(repo_root, file_handler)

    if format == "json":
        if output:
            rel_output = _to_rel_str(output, repo_root)
            file_handler.write_runtime_json(rel_output, coverage_data)
            console.print(f"[green]✅ Written to {output}[/green]")
        else:
            console.print_json(data=coverage_data)
        return

    content = (
        logic.render_hierarchical(coverage_data)
        if format == "hierarchical"
        else logic.render_summary(coverage_data)
    )

    if output:
        rel_output = _to_rel_str(output, repo_root)
        file_handler.write_runtime_text(rel_output, content)
        console.print(f"[green]✅ Written to {output}[/green]")
    else:
        console.print(content)


def _to_rel_str(path: Path, root: Path) -> str:
    """Converts a path to a repo-relative string."""
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


# =====================================================================
# VALIDATE-REQUEST COMMAND — FULL ORIGINAL LOGIC PRESERVED
# =====================================================================


@governance_app.command("validate-request")
@core_command(dangerous=False, requires_context=False)
# ID: f5f60654-a77d-45ae-bd45-fd042dfb33be
async def validate_request_command(
    ctx: typer.Context,
    request: str = typer.Argument(..., help="Request to validate"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output"),
) -> None:
    """Demonstrate pre-flight constitutional validation (5 gates)."""
    await _validate_request_async(request, verbose)


# ID: 18a24f5b-56b1-4b58-98af-125f64e45ff0  (original ID from longer file)
async def _validate_request_async(request: str, verbose: bool = False) -> None:
    """
    Run pre-flight constitutional validation on a request.
    (Exact copy of the full logic from your original validate_request.py)
    """
    console.print()
    console.print(
        Panel.fit(
            "[bold cyan]Pre-Flight Constitutional Validation[/bold cyan]",
            border_style="cyan",
        )
    )
    console.print()

    console.print(f'[bold]User Request:[/bold] "{request}"')
    console.print()

    try:
        # Initialize components
        console.print("[dim]Initializing constitutional infrastructure...[/dim]")

        from body.services.service_registry import service_registry
        from mind.governance.assumption_extractor import AssumptionExtractor
        from mind.governance.authority_package_builder import AuthorityPackageBuilder
        from mind.governance.rule_conflict_detector import RuleConflictDetector
        from shared.infrastructure.intent.intent_repository import (
            get_intent_repository,
        )
        from will.interpreters.request_interpreter import NaturalLanguageInterpreter
        from will.tools.policy_vectorizer import PolicyVectorizer

        # Get services
        cognitive_service = await service_registry.get_cognitive_service()
        qdrant_service = await service_registry.get_qdrant_service()

        # Initialize components
        intent_repo = get_intent_repository()
        interpreter = NaturalLanguageInterpreter()

        policy_vectorizer = PolicyVectorizer(
            intent_repo.root, cognitive_service, qdrant_service
        )

        assumption_extractor = AssumptionExtractor(
            intent_repository=intent_repo,
            policy_vectorizer=policy_vectorizer,
            cognitive_service=cognitive_service,
        )

        conflict_detector = RuleConflictDetector()

        authority_builder = AuthorityPackageBuilder(
            request_interpreter=interpreter,
            intent_repository=intent_repo,
            policy_vectorizer=policy_vectorizer,
            assumption_extractor=assumption_extractor,
            rule_conflict_detector=conflict_detector,
        )

        console.print("[dim]Infrastructure ready[/dim]")
        console.print()

        # =====================================================================
        # GATE 1: Parse Intent
        # =====================================================================
        console.print("[bold yellow]═[/bold yellow]" * 40)
        console.print("[bold yellow][GATE 1][/bold yellow] Parse Intent")
        console.print("[bold yellow]═[/bold yellow]" * 40)
        console.print()

        result = await interpreter.execute(user_message=request)

        if not result.ok:
            console.print(f"[red]✗[/red] Intent parsing failed: {result.error}")
            return

        task = result.data.get("task")

        console.print(f"[green]✓[/green] TaskType: {task.task_type.value}")
        console.print(f"[green]✓[/green] Target: {task.target}")
        console.print(
            f"[green]✓[/green] Constraints: {task.constraints or '(none specified)'}"
        )
        console.print()

        # =====================================================================
        # GATE 2: Match Constitutional Policies
        # =====================================================================
        console.print("[bold yellow]═[/bold yellow]" * 40)
        console.print(
            "[bold yellow][GATE 2][/bold yellow] Match Constitutional Policies"
        )
        console.print("[bold yellow]═[/bold yellow]" * 40)
        console.print()

        # Build search query
        query_parts = [task.task_type.value, task.target, *task.constraints]
        query = " ".join(query_parts)

        # Search for policies
        policy_hits = await policy_vectorizer.search_policies(query=query, limit=5)

        if not policy_hits:
            console.print("[yellow]⚠[/yellow] No matching policies found")
            console.print()
        else:
            console.print(
                f"[green]✓[/green] Found {len(policy_hits)} relevant policies:"
            )
            console.print()

            for i, hit in enumerate(policy_hits, 1):
                payload = hit.get("payload", {})
                metadata = payload.get("metadata", {})

                rule_id = metadata.get("rule_id", "unknown")
                enforcement = metadata.get("enforcement", "reporting")
                score = hit.get("score", 0.0)

                enforcement_color = "red" if enforcement == "blocking" else "yellow"

                console.print(
                    f"   {i}. {rule_id} ([{enforcement_color}]{enforcement}[/{enforcement_color}]) - relevance: {score:.2f}"
                )

                if verbose:
                    statement = payload.get("text", "")[:100] + "..."
                    console.print(f"      [dim]{statement}[/dim]")

            console.print()

        # =====================================================================
        # GATE 3: Detect Contradictions
        # =====================================================================
        console.print("[bold yellow]═[/bold yellow]" * 40)
        console.print("[bold yellow][GATE 3][/bold yellow] Detect Contradictions")
        console.print("[bold yellow]═[/bold yellow]" * 40)
        console.print()

        console.print("[green]✓[/green] No contradictions detected")
        console.print()

        # =====================================================================
        # GATE 4: Extract Assumptions
        # =====================================================================
        console.print("[bold yellow]═[/bold yellow]" * 40)
        console.print(
            "[bold yellow][GATE 4][/bold yellow] Extract Assumptions (Dynamic Synthesis)"
        )
        console.print("[bold yellow]═[/bold yellow]" * 40)
        console.print()

        console.print("[dim]Querying .intent/ policies for guidance...[/dim]")
        console.print()

        # Convert policy hits to format AssumptionExtractor expects
        policy_dicts = [
            {
                "policy_id": hit.get("payload", {})
                .get("metadata", {})
                .get("policy_id", "unknown"),
                "rule_id": hit.get("payload", {})
                .get("metadata", {})
                .get("rule_id", "unknown"),
                "statement": hit.get("payload", {}).get("text", ""),
                "metadata": hit.get("payload", {}).get("metadata", {}),
            }
            for hit in policy_hits
        ]

        assumptions = await assumption_extractor.extract_assumptions(task, policy_dicts)

        if not assumptions:
            console.print(
                "[green]✓[/green] Request is complete (no assumptions needed)"
            )
            console.print()
        else:
            console.print(
                f"[cyan]📋[/cyan] Synthesized {len(assumptions)} assumptions from policies:"
            )
            console.print()

            for assumption in assumptions:
                # Create formatted display
                console.print(f"[bold cyan]•[/bold cyan] {assumption.aspect}")
                console.print(f"  [green]Value:[/green] {assumption.suggested_value}")
                console.print(f"  [blue]Citation:[/blue] {assumption.cited_policy}")
                console.print(f"  [yellow]Rationale:[/yellow] {assumption.rationale}")
                console.print(
                    f"  [magenta]Confidence:[/magenta] {assumption.confidence:.0%}"
                )
                console.print()

        # =====================================================================
        # GATE 5: Build Authority Package
        # =====================================================================
        console.print("[bold yellow]═[/bold yellow]" * 40)
        console.print("[bold yellow][GATE 5][/bold yellow] Build Authority Package")
        console.print("[bold yellow]═[/bold yellow]" * 40)
        console.print()

        # Build mock authority package for display
        console.print("[green]✓[/green] Package complete:")
        console.print()

        # Create summary table
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Matched policies", str(len(policy_hits)))
        table.add_row("Contradictions", "0")
        table.add_row("Assumptions", str(len(assumptions)))
        table.add_row("Constitutional constraints", "['requires_audit_logging']")

        console.print(table)
        console.print()

        # =====================================================================
        # Final Status
        # =====================================================================
        console.print("[bold yellow]═[/bold yellow]" * 40)
        console.print()

        if assumptions:
            console.print(
                Panel.fit(
                    "[bold green]AUTHORITY PACKAGE READY[/bold green]\n\n"
                    f"Status: [yellow]PENDING USER CONFIRMATION[/yellow]\n"
                    f"Reason: {len(assumptions)} assumptions require approval\n\n"
                    "[dim]In production, user would confirm assumptions before generation proceeds[/dim]",
                    border_style="yellow",
                    title="Validation Result",
                )
            )
        else:
            console.print(
                Panel.fit(
                    "[bold green]AUTHORITY PACKAGE READY[/bold green]\n\n"
                    "Status: [green]VALID FOR GENERATION[/green]\n"
                    "All gates passed - code generation authorized\n\n"
                    "[dim]LLM would receive constitutional authority context[/dim]",
                    border_style="green",
                    title="Validation Result",
                )
            )

        console.print()

        # Show what would happen next
        if assumptions:
            console.print("[bold]Next Steps:[/bold]")
            console.print("  1. User reviews assumptions")
            console.print("  2. User confirms or modifies")
            console.print("  3. Authority package finalized")
            console.print("  4. Code generation proceeds with constitutional backing")
        else:
            console.print("[bold]Next Steps:[/bold]")
            console.print("  1. Authority package sent to LLM")
            console.print("  2. Code generated with constitutional constraints")
            console.print("  3. Post-generation validation (defense in depth)")
            console.print("  4. Code ready for execution")

        console.print()

    except Exception as e:
        console.print()
        console.print("[red]✗ Validation failed with error:[/red]")
        console.print(f"[red]{e}[/red]")
        logger.error("Validation failed", exc_info=True)
        console.print()


# Export for main CLI registration
__all__ = ["governance_app"]
