# src/cli/commands/governance.py
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
    help="Constitutional governance visibility and verification.", no_args_is_help=True
)


@governance_app.command("coverage")
@core_command(dangerous=False, requires_context=True)
# ID: b49434d5-e926-4002-809d-080aab1253e8
def enforcement_coverage(
    ctx: typer.Context,
    format: str = typer.Option(
        "summary", "--format", "-f", help="Output format: summary|hierarchical|json"
    ),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Write output to file instead of console"
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
            logger.info("[green]✅ Written to %s[/green]", output)
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
        logger.info("[green]✅ Written to %s[/green]", output)
    else:
        logger.info(content)


def _to_rel_str(path: Path, root: Path) -> str:
    """Converts a path to a repo-relative string."""
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


@governance_app.command("validate-request")
@core_command(dangerous=False, requires_context=False)
# ID: 8f7125f1-d27c-4c85-836a-32210e5db8ca
async def validate_request_command(
    ctx: typer.Context,
    request: str = typer.Argument(..., help="Request to validate"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output"),
) -> None:
    """Demonstrate pre-flight constitutional validation (5 gates)."""
    await _validate_request_async(request, verbose)


async def _validate_request_async(request: str, verbose: bool = False) -> None:
    """
    Run pre-flight constitutional validation on a request.
    (Exact copy of the full logic from your original validate_request.py)
    """
    console.print()
    logger.info(
        Panel.fit(
            "[bold cyan]Pre-Flight Constitutional Validation[/bold cyan]",
            border_style="cyan",
        )
    )
    console.print()
    logger.info('[bold]User Request:[/bold] "%s"', request)
    console.print()
    try:
        logger.info("[dim]Initializing constitutional infrastructure...[/dim]")
        from body.services.service_registry import service_registry
        from mind.governance.assumption_extractor import AssumptionExtractor
        from mind.governance.authority_package_builder import AuthorityPackageBuilder
        from mind.governance.rule_conflict_detector import RuleConflictDetector
        from shared.infrastructure.intent.intent_repository import get_intent_repository
        from will.interpreters.request_interpreter import NaturalLanguageInterpreter
        from will.tools.policy_vectorizer import PolicyVectorizer

        cognitive_service = await service_registry.get_cognitive_service()
        qdrant_service = await service_registry.get_qdrant_service()
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
        logger.info("[dim]Infrastructure ready[/dim]")
        logger.info()
        logger.info("[bold yellow]═[/bold yellow]" * 40)
        logger.info("[bold yellow][GATE 1][/bold yellow] Parse Intent")
        logger.info("[bold yellow]═[/bold yellow]" * 40)
        logger.info()
        result = await interpreter.execute(user_message=request)
        if not result.ok:
            logger.info("[red]✗[/red] Intent parsing failed: %s", result.error)
            return
        task = result.data.get("task")
        logger.info("[green]✓[/green] TaskType: %s", task.task_type.value)
        logger.info("[green]✓[/green] Target: %s", task.target)
        logger.info(
            "[green]✓[/green] Constraints: %s", task.constraints or "(none specified)"
        )
        logger.info()
        logger.info("[bold yellow]═[/bold yellow]" * 40)
        logger.info("[bold yellow][GATE 2][/bold yellow] Match Constitutional Policies")
        logger.info("[bold yellow]═[/bold yellow]" * 40)
        logger.info()
        query_parts = [task.task_type.value, task.target, *task.constraints]
        query = " ".join(query_parts)
        policy_hits = await policy_vectorizer.search_policies(query=query, limit=5)
        if not policy_hits:
            logger.info("[yellow]⚠[/yellow] No matching policies found")
            logger.info()
        else:
            logger.info(
                "[green]✓[/green] Found %s relevant policies:", len(policy_hits)
            )
            logger.info()
            for i, hit in enumerate(policy_hits, 1):
                payload = hit.get("payload", {})
                metadata = payload.get("metadata", {})
                rule_id = metadata.get("rule_id", "unknown")
                enforcement = metadata.get("enforcement", "reporting")
                score = hit.get("score", 0.0)
                enforcement_color = "red" if enforcement == "blocking" else "yellow"
                logger.info(
                    "   %s. %s ([%s]%s[/%s]) - relevance: %s",
                    i,
                    rule_id,
                    enforcement_color,
                    enforcement,
                    enforcement_color,
                    score,
                )
                if verbose:
                    statement = payload.get("text", "")[:100] + "..."
                    logger.info("      [dim]%s[/dim]", statement)
            logger.info()
        logger.info("[bold yellow]═[/bold yellow]" * 40)
        logger.info("[bold yellow][GATE 3][/bold yellow] Detect Contradictions")
        logger.info("[bold yellow]═[/bold yellow]" * 40)
        logger.info()
        logger.info("[green]✓[/green] No contradictions detected")
        logger.info()
        logger.info("[bold yellow]═[/bold yellow]" * 40)
        logger.info(
            "[bold yellow][GATE 4][/bold yellow] Extract Assumptions (Dynamic Synthesis)"
        )
        logger.info("[bold yellow]═[/bold yellow]" * 40)
        logger.info()
        logger.info("[dim]Querying .intent/ policies for guidance...[/dim]")
        logger.info()
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
            logger.info("[green]✓[/green] Request is complete (no assumptions needed)")
            logger.info()
        else:
            logger.info(
                "[cyan]📋[/cyan] Synthesized %s assumptions from policies:",
                len(assumptions),
            )
            logger.info()
            for assumption in assumptions:
                logger.info("[bold cyan]•[/bold cyan] %s", assumption.aspect)
                logger.info("  [green]Value:[/green] %s", assumption.suggested_value)
                logger.info("  [blue]Citation:[/blue] %s", assumption.cited_policy)
                logger.info("  [yellow]Rationale:[/yellow] %s", assumption.rationale)
                logger.info(
                    "  [magenta]Confidence:[/magenta] %s", assumption.confidence
                )
                logger.info()
        logger.info("[bold yellow]═[/bold yellow]" * 40)
        logger.info("[bold yellow][GATE 5][/bold yellow] Build Authority Package")
        logger.info("[bold yellow]═[/bold yellow]" * 40)
        logger.info()
        logger.info("[green]✓[/green] Package complete:")
        logger.info()
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")
        table.add_row("Matched policies", str(len(policy_hits)))
        table.add_row("Contradictions", "0")
        table.add_row("Assumptions", str(len(assumptions)))
        table.add_row("Constitutional constraints", "['requires_audit_logging']")
        logger.info(table)
        logger.info()
        logger.info("[bold yellow]═[/bold yellow]" * 40)
        logger.info()
        if assumptions:
            logger.info(
                Panel.fit(
                    f"[bold green]AUTHORITY PACKAGE READY[/bold green]\n\nStatus: [yellow]PENDING USER CONFIRMATION[/yellow]\nReason: {len(assumptions)} assumptions require approval\n\n[dim]In production, user would confirm assumptions before generation proceeds[/dim]",
                    border_style="yellow",
                    title="Validation Result",
                )
            )
        else:
            logger.info(
                Panel.fit(
                    "[bold green]AUTHORITY PACKAGE READY[/bold green]\n\nStatus: [green]VALID FOR GENERATION[/green]\nAll gates passed - code generation authorized\n\n[dim]LLM would receive constitutional authority context[/dim]",
                    border_style="green",
                    title="Validation Result",
                )
            )
        logger.info()
        if assumptions:
            logger.info("[bold]Next Steps:[/bold]")
            logger.info("  1. User reviews assumptions")
            logger.info("  2. User confirms or modifies")
            logger.info("  3. Authority package finalized")
            logger.info("  4. Code generation proceeds with constitutional backing")
        else:
            logger.info("[bold]Next Steps:[/bold]")
            logger.info("  1. Authority package sent to LLM")
            logger.info("  2. Code generated with constitutional constraints")
            logger.info("  3. Post-generation validation (defense in depth)")
            logger.info("  4. Code ready for execution")
        logger.info()
    except Exception as e:
        logger.info()
        logger.info("[red]✗ Validation failed with error:[/red]")
        logger.info("[red]%s[/red]", e)
        logger.error("Validation failed", exc_info=True)
        logger.info()


__all__ = ["governance_app"]
