# src/cli/resources/grc/gap_analysis.py
"""`core-admin grc gap-analysis <corpus>` — the customer-facing GRC demo.

Points the constitutional engine at a folder of documents (the customer's
"documentation stack") and prints a gap report against a compliance
requirements catalog. Each requirement is evaluated corpus-wide (ADR-118 D1)
and every verdict is honestly labelled by how it was established — proven /
judged / needs-human (ADR-113) — and what it found — satisfied / deficient /
not covered / needs human / unavailable (ADR-118 D3).

Read-only: it reads the corpus and reports; it never modifies the documents.
"""

from __future__ import annotations

import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from body.services.grc import (
    GRCGapAnalysisService,
    build_framework_descriptor,
    load_catalog,
    load_catalog_meta,
)
from cli.utils import core_command
from shared.ai.prompt_model import PromptModel
from shared.logger import getLogger
from shared.models import (
    Applicability,
    ApplicabilityAssessment,
    EvidenceClass,
    RequirementStatus,
    RequirementVerdict,
)

from . import app


logger = getLogger(__name__)
console = Console()

_APPLICABILITY_STYLE = {
    Applicability.IN_SCOPE: "[green]in scope[/green]",
    Applicability.OUT_OF_SCOPE: "[bold red]out of scope[/bold red]",
    Applicability.UNCERTAIN: "[yellow]uncertain[/yellow]",
}

_EVIDENCE_STYLE = {
    EvidenceClass.PROVEN: "[green]proven[/green]",
    EvidenceClass.JUDGED: "[yellow]judged[/yellow]",
    EvidenceClass.ATTESTED: "[magenta]needs human[/magenta]",
}

_STATUS_STYLE = {
    RequirementStatus.SATISFIED: "[green]satisfied[/green]",
    RequirementStatus.DEFICIENT: "[bold red]DEFICIENT[/bold red]",
    RequirementStatus.NOT_COVERED: "[bold red]NOT COVERED[/bold red]",
    RequirementStatus.COVERED_UNAUTHORITATIVELY: "[red]covered (unauthoritatively)[/red]",
    RequirementStatus.NOT_APPLICABLE: "[dim]not applicable[/dim]",
    RequirementStatus.NEEDS_HUMAN: "[magenta]needs human sign-off[/magenta]",
    RequirementStatus.UNAVAILABLE: "[bold yellow]verdict unavailable[/bold yellow]",
}

_GAP_STATUSES = {
    RequirementStatus.DEFICIENT,
    RequirementStatus.NOT_COVERED,
    RequirementStatus.COVERED_UNAUTHORITATIVELY,
}


# ID: 89ed39b5-d619-4489-99e9-9b1c9852b29e
def _render_applicability(catalog: str, assessment: ApplicabilityAssessment) -> None:
    """Surface the applicability gate's verdict (the 'suggest' step, ADR-118 D2)."""
    domains = ", ".join(assessment.detected_domains) or "undetermined"
    verdict = _APPLICABILITY_STYLE.get(
        assessment.applicability, str(assessment.applicability)
    )
    console.print(
        f"[bold]Applicability[/bold] [dim](judged)[/dim] — catalog "
        f"[bold]{catalog}[/bold] is {verdict} for this corpus "
        f"[dim](reads as: {domains})[/dim]"
    )
    if assessment.rationale:
        console.print(f"  [dim]{assessment.rationale}[/dim]")


# ID: 00bb5176-1308-4695-a0c2-02ffbcbe5295
def _render_report(corpus: Path, results: list[RequirementVerdict]) -> None:
    """Print the traceability matrix: requirement → evidence class → status → detail."""
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
        if r.status in _GAP_STATUSES:
            # Surface the first evidence cite, fall back to rationale.
            detail = r.evidence[0].cite if r.evidence else r.rationale
        elif r.status is RequirementStatus.UNAVAILABLE:
            detail = r.rationale
        elif r.status is RequirementStatus.NEEDS_HUMAN:
            detail = r.rationale
        else:
            detail = r.rationale or ""

        table.add_row(
            r.statement,
            _EVIDENCE_STYLE.get(r.evidence_class, str(r.evidence_class)),
            _STATUS_STYLE.get(r.status, str(r.status)),
            detail,
        )

    console.print(table)

    gaps = sum(1 for r in results if r.is_gap)
    human = sum(1 for r in results if r.status is RequirementStatus.NEEDS_HUMAN)
    unavailable = sum(1 for r in results if r.status is RequirementStatus.UNAVAILABLE)
    not_applicable = sum(
        1 for r in results if r.status is RequirementStatus.NOT_APPLICABLE
    )
    console.print(
        f"\n[bold]{len(results)} requirements[/bold] · "
        f"[red]{gaps} gap(s)[/red] · "
        f"[magenta]{human} need human sign-off[/magenta] · "
        f"[bold yellow]{unavailable} verdict unavailable[/bold yellow]"
        + (f" · [dim]{not_applicable} not applicable[/dim]" if not_applicable else "")
    )
    console.print(
        "[dim]Every line states how its verdict was reached. CORE reports only "
        "what it can defend — proven, judged, or handed to your reviewer.[/dim]"
    )


@app.command("gap-analysis")
@core_command(dangerous=False, requires_context=True)
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
        "nist_800_171",
        "--catalog",
        "-c",
        help="Requirements catalog to check against (a framework under grc-catalogs/).",
    ),
    assume_applicable: bool = typer.Option(
        False,
        "--assume-applicable",
        "-y",
        help=(
            "Skip the applicability confirm step — score even if the framework "
            "reads as out of domain for this corpus."
        ),
    ),
) -> None:
    """Run a compliance requirements catalog against a folder of documents.

    Produces a gap report where each requirement is evaluated corpus-wide
    (ADR-118 D1) and labelled by how its verdict was established: proven
    (deterministic), judged (AI), or attested (needs a human). Silence from
    individual documents is not a gap — only corpus-level non-coverage is (D4).
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

    # Wire the GRC judge: resolve an LLM client for the grc_judge prompt's
    # cognitive role via the cognitive service (Will owns client construction;
    # Body receives it by DI). Best-effort — if no client can be obtained,
    # judged requirements degrade honestly to "verdict unavailable" rather
    # than failing the run.
    llm_client = None
    try:
        role = PromptModel.load("grc_judge").manifest.role
        cognitive = getattr(ctx.obj, "cognitive_service", None)
        if cognitive is not None:
            llm_client = await cognitive.aget_client_for_role(role)
    except Exception as exc:  # degrade honestly, never hard-fail
        logger.warning("GRC judge LLM client unavailable: %s", exc)
        console.print(
            "[dim]No LLM judge wired — judged requirements will report "
            "'verdict unavailable'.[/dim]"
        )

    service = GRCGapAnalysisService(llm_client=llm_client)

    # Applicability gate (ADR-118 D2): detect → suggest → confirm domain fit
    # BEFORE scoring, so CORE never produces a confidently-useless "not covered
    # everywhere" report for an out-of-domain pairing.
    descriptor = build_framework_descriptor(load_catalog_meta(catalog))
    assessment = await service.assess_applicability(
        corpus.resolve(), framework_id=catalog, framework_descriptor=descriptor
    )
    _render_applicability(catalog, assessment)

    # Only a clear out-of-domain verdict blocks; "uncertain" warns but proceeds
    # (blocking every thin corpus would cripple the tool). The confirm step is
    # skipped under --assume-applicable.
    if assessment.applicability is Applicability.OUT_OF_SCOPE and not assume_applicable:
        proceed = sys.stdin.isatty() and typer.confirm(
            "This framework reads as out of domain for the corpus. Score it anyway?",
            default=False,
        )
        if not proceed:
            console.print(
                f"\n[bold]{len(rules)} requirements were not assessed[/bold] — "
                f"this corpus reads as a different domain than [bold]{catalog}[/bold] "
                "governs. Re-run with [bold]--assume-applicable[/bold] to override "
                "if the domain detection is wrong."
            )
            return

    results = await service.run(corpus.resolve(), catalog=rules)
    _render_report(corpus, results)
