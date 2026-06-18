# src/cli/resources/grc/gap_analysis.py
"""`core-admin grc gap-analysis <corpus>` — the customer-facing GRC demo.

Points the constitutional engine at a folder of documents (the customer's
"documentation stack") and prints a gap report against a compliance
requirements catalog, with every line honestly labelled by how its verdict was
established — proven / judged / needs-human (ADR-113).

Read-only: it reads the corpus and reports; it never modifies the documents.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from body.services.grc import (
    GRCGapAnalysisService,
    RequirementResult,
    load_catalog,
)
from cli.utils import core_command
from shared.models import EvidenceClass

from . import app


console = Console()

_EVIDENCE_STYLE = {
    EvidenceClass.PROVEN: "[green]proven[/green]",
    EvidenceClass.JUDGED: "[yellow]judged[/yellow]",
    EvidenceClass.ATTESTED: "[magenta]needs human[/magenta]",
}

_STATUS_STYLE = {
    "gap": "[bold red]GAP[/bold red]",
    "met": "[green]met[/green]",
    "needs_human": "[magenta]needs human sign-off[/magenta]",
    "pending_ai": "[yellow]AI evaluation pending[/yellow]",
}


# ID: 00bb5176-1308-4695-a0c2-02ffbcbe5295
def _render_report(corpus: Path, results: list[RequirementResult]) -> None:
    """Print the traceability matrix: requirement → evidence class → status."""
    table = Table(
        title=f"[bold]GRC Gap Report[/bold] — {corpus}",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Requirement", style="cyan", overflow="fold")
    table.add_column("Evidence", style="white")
    table.add_column("Status", style="white")
    table.add_column("Detail", style="white", overflow="fold")

    for r in results:
        if r.status == "gap":
            detail = r.findings[0].message if r.findings else ""
        elif r.status == "needs_human":
            prompt = (
                r.findings[0].context.get("attestation_prompt", "")
                if r.findings
                else ""
            )
            detail = prompt
        elif r.status == "pending_ai":
            detail = "Requires an AI evaluation pass (run with an LLM provider wired)."
        else:
            detail = "No gap found by the deterministic check."
        table.add_row(
            r.statement,
            _EVIDENCE_STYLE.get(r.evidence_class, str(r.evidence_class)),
            _STATUS_STYLE.get(r.status, r.status),
            detail,
        )

    console.print(table)

    gaps = sum(1 for r in results if r.status == "gap")
    human = sum(1 for r in results if r.status == "needs_human")
    pending = sum(1 for r in results if r.status == "pending_ai")
    console.print(
        f"\n[bold]{len(results)} requirements[/bold] · "
        f"[red]{gaps} gap(s) proven[/red] · "
        f"[magenta]{human} need human sign-off[/magenta] · "
        f"[yellow]{pending} pending AI[/yellow]"
    )
    console.print(
        "[dim]Every line states how its verdict was reached. CORE reports only "
        "what it can defend — proven, judged, or handed to your reviewer.[/dim]"
    )


@app.command("gap-analysis")
@core_command(dangerous=False, requires_context=False, offline_capable=True)
# ID: 67729121-d5f3-4fd5-95ae-62eac24a1e8e
async def gap_analysis(
    ctx: typer.Context,
    corpus: Path = typer.Argument(
        ...,
        help="Folder of documents to analyse (the customer's documentation stack).",
        exists=True,
        file_okay=False,
        dir_okay=True,
    ),
    catalog: str = typer.Option(
        "nist_800_171_min",
        "--catalog",
        "-c",
        help="Requirements catalog to check against (see src/body/services/grc/catalogs/).",
    ),
) -> None:
    """Run a compliance requirements catalog against a folder of documents.

    Produces a gap report where each requirement is labelled by how its verdict
    was established: proven (deterministic), judged (AI), or attested (needs a
    human). The default catalog is a minimal, regulation-derived NIST SP 800-171
    subset; statements are CORE-authored paraphrases citing control IDs, not the
    standard's text.
    """
    console.print(
        f"[bold cyan]🔎 GRC gap-analysis[/bold cyan] over [bold]{corpus}[/bold] "
        f"[dim](catalog: {catalog})[/dim]"
    )
    try:
        rules = load_catalog(catalog)
    except FileNotFoundError as exc:
        console.print(f"[bold red]{exc}[/bold red]")
        raise typer.Exit(2) from exc
    results = await GRCGapAnalysisService().run(corpus.resolve(), catalog=rules)
    _render_report(corpus, results)
