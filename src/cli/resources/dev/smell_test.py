# src/cli/resources/dev/smell_test.py

"""
core-admin dev smell-test — Shadow KG consequence-sensing CLI.

Octopus paper Phase 1 (Sensation Layer) end-to-end demonstration. Given a
single proposed file change, builds a shadow workspace, runs the
constitutional audit + knowledge graph over both disk and shadow, and prints
the deltas:

  - new constitutional findings introduced by the proposed change
  - existing findings the proposed change resolves
  - structural symbol-graph diff (added / removed / signature changes)
  - shadow-graph callers that orphan repo-internal names

This is the load-bearing demo that the Shadow KG primitive is real and CORE-
shaped. It is a SMELL TEST ONLY — no commit, no autonomy, no reflex loop.
The V2.3-REBIRTH reflex loop will consume the same audit + structural diff
as its pain signal, but that comes later.

Exit codes:
    0 - clean: no new findings, no orphaned callers
    1 - new constitutional findings introduced
    2 - structurally orphaned callers but no new findings (belt-and-braces
        catch — the audit engine missed something the symbol graph saw)
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from cli.utils import core_command
from mind.governance.shadow_audit import run_shadow_audit
from shared.infrastructure.context.limb_workspace import LimbWorkspace
from shared.infrastructure.context.shadow_audit_diff import (
    FindingRef,
    ShadowAuditDiff,
)
from shared.infrastructure.context.shadow_diff import ShadowDiff, SymbolRef
from shared.infrastructure.context.shadow_materializer import (
    materialize_workspace_for_audit,
)
from shared.infrastructure.intent.intent_repository import get_intent_repository
from shared.infrastructure.knowledge_graph_service import KnowledgeGraphBuilder
from shared.path_utils import get_repo_root

from .hub import app


console = Console()


@app.command("smell-test")
@core_command(dangerous=False, requires_context=False, offline_capable=True)
# ID: 18d85719-0854-4a98-86cd-63517ccf37b2
async def smell_test_command(
    ctx: typer.Context,
    file: str = typer.Option(
        ...,
        "--file",
        "-f",
        help=(
            "Repo-relative path of the file the crate overlays. Must be under "
            "src/ in v1 — other prefixes are guarded against to prevent the "
            "shadow materializer writing through directory symlinks into the "
            "real repo."
        ),
    ),
    content_from: Path = typer.Option(
        ...,
        "--content-from",
        "-c",
        help=(
            "Local file whose contents become the crate-overlaid content for "
            "--file. The file on disk is NOT modified; this is purely the "
            "proposed-change input the Limb would sense."
        ),
    ),
) -> None:
    """Sense constitutional + structural consequences of a proposed file change.

    Builds a shadow workspace where <file> contains <content-from>'s content,
    runs disk + shadow constitutional audits, runs disk + shadow knowledge
    graphs, and reports the deltas. Octopus paper Phase 1 — pure sensation,
    no autonomy, no commit.
    """
    repo_root = get_repo_root()

    if not file.startswith("src/"):
        console.print(
            f"[red]error:[/red] --file must be under src/ for v1 (got {file!r}). "
            "The shadow materializer per-file symlinks src/; other prefixes are "
            "directory-symlinked and would write through into the real repo."
        )
        raise typer.Exit(64)

    content_from = content_from.resolve()
    if not content_from.is_file():
        console.print(
            f"[red]error:[/red] --content-from is not a readable file: {content_from}"
        )
        raise typer.Exit(64)

    proposed_content = content_from.read_text(encoding="utf-8")
    workspace = LimbWorkspace(repo_root, crate_files={file: proposed_content})

    console.rule("[bold cyan]Shadow KG Smell Test[/bold cyan]")
    console.print(f"  [dim]repo[/dim]         {repo_root}")
    console.print(f"  [dim]proposed[/dim]     {file}")
    console.print(f"  [dim]content from[/dim] {content_from}")
    console.print()

    intent_repo = get_intent_repository()

    with console.status("[cyan]Building disk knowledge graph…"):
        disk_kg = KnowledgeGraphBuilder(repo_root).build()
    with console.status("[cyan]Building shadow knowledge graph…"):
        shadow_kg = KnowledgeGraphBuilder(repo_root, workspace=workspace).build()
    shadow_diff = ShadowDiff(disk_kg, shadow_kg)

    # Both runs use the static-engine cohort (run_shadow_audit) so the
    # diff is computed over identical rule sets. Runtime-introspection
    # engines (cli_gate / knowledge_gate / runtime_gate / llm_gate) are
    # partitioned out on principle: they ask post-commit questions and
    # cannot honestly sense a pre-commit shadow workspace. See module
    # docstring on mind.governance.shadow_audit for the category split.
    with console.status("[cyan]Running disk audit (static cohort)…"):
        disk_result = await run_shadow_audit(
            intent_repo=intent_repo, repo_path=repo_root
        )

    with console.status("[cyan]Materializing shadow tempdir…"):
        with materialize_workspace_for_audit(workspace, repo_root) as shadow_root:
            console.print(f"  [dim]shadow at[/dim]   {shadow_root}")
            with console.status("[cyan]Running shadow audit (static cohort)…"):
                shadow_result = await run_shadow_audit(
                    intent_repo=intent_repo, repo_path=shadow_root
                )

    _render_partition(disk_result.get("skipped_rules", []))

    audit_diff = ShadowAuditDiff(
        disk_findings=disk_result["findings"],
        shadow_findings=shadow_result["findings"],
    )

    _render_audit_diff(audit_diff)
    _render_structural_diff(shadow_diff)
    exit_code = _render_verdict_and_compute_exit(audit_diff, shadow_diff)
    raise typer.Exit(exit_code)


def _render_partition(skipped_rules: list[dict[str, str]]) -> None:
    """Surface the static/runtime engine partition so the user knows
    what the smell-test does NOT sense. This is principled exclusion —
    runtime engines ask post-commit questions; see shadow_audit module
    docstring for the category distinction.
    """
    if not skipped_rules:
        return
    by_engine: dict[str, int] = {}
    reasons: dict[str, str] = {}
    for rule in skipped_rules:
        engine = rule.get("engine", "?")
        by_engine[engine] = by_engine.get(engine, 0) + 1
        reasons.setdefault(engine, rule.get("reason", ""))
    console.print()
    console.rule("[bold]Engine partition (pre-commit cohort)[/bold]")
    for engine in sorted(by_engine):
        console.print(
            f"  [dim]skipped[/dim] [yellow]{engine}[/yellow] "
            f"({by_engine[engine]} rule{'s' if by_engine[engine] != 1 else ''}) — "
            f"{reasons[engine]}"
        )


def _render_audit_diff(audit_diff: ShadowAuditDiff) -> None:
    console.print()
    console.rule("[bold]Constitutional audit delta[/bold]")
    new = audit_diff.new_findings()
    resolved = audit_diff.resolved_findings()

    if not new and not resolved:
        console.print(
            "  [green]No constitutional change.[/green] "
            "The proposed change neither introduces nor resolves audit findings."
        )
        return

    if new:
        console.print(f"  [red]NEW findings ({len(new)}):[/red]")
        console.print(_finding_table(new))
    if resolved:
        console.print(f"  [green]RESOLVED findings ({len(resolved)}):[/green]")
        console.print(_finding_table(resolved))


def _render_structural_diff(shadow_diff: ShadowDiff) -> None:
    console.print()
    console.rule("[bold]Structural symbol-graph delta[/bold]")
    added = shadow_diff.added_symbols()
    removed = shadow_diff.removed_symbols()
    changed = shadow_diff.changed_signatures()
    orphans = shadow_diff.orphaned_callers()

    if shadow_diff.is_empty():
        console.print(
            "  [green]No structural change.[/green] "
            "Symbol graph is identical between disk and shadow."
        )
        return

    if added:
        console.print(f"  [cyan]ADDED symbols ({len(added)}):[/cyan]")
        console.print(_symbol_list(added))
    if removed:
        console.print(f"  [yellow]REMOVED symbols ({len(removed)}):[/yellow]")
        console.print(_symbol_list(removed))
    if changed:
        console.print(f"  [yellow]CHANGED signatures ({len(changed)}):[/yellow]")
        for delta in changed:
            console.print(
                f"    [dim]{delta.symbol_path}[/dim]\n"
                f"      disk:   {delta.disk_parameters}\n"
                f"      shadow: {delta.shadow_parameters}"
            )
    if orphans:
        console.print(f"  [red]ORPHANED callers ({len(orphans)}):[/red]")
        for o in orphans:
            console.print(
                f"    [red]{o.caller_symbol_path}[/red] "
                f"calls now-undefined [bold]{o.orphaned_call}[/bold]"
            )


def _render_verdict_and_compute_exit(
    audit_diff: ShadowAuditDiff, shadow_diff: ShadowDiff
) -> int:
    console.print()
    new = audit_diff.new_findings()
    orphans = shadow_diff.orphaned_callers()

    if not new and not orphans:
        console.print(
            Panel.fit(
                "[green]VERDICT: clean[/green] — the proposed change introduces "
                "no new constitutional findings and no structural orphans.",
                border_style="green",
            )
        )
        return 0

    if new:
        console.print(
            Panel.fit(
                f"[red]VERDICT: new constitutional findings ({len(new)})[/red] — "
                "the proposed change would introduce harm the Governor's audit "
                "already disallows.",
                border_style="red",
            )
        )
        return 1

    console.print(
        Panel.fit(
            f"[yellow]VERDICT: structural orphans ({len(orphans)})[/yellow] — "
            "the audit found no new findings but the symbol graph reports calls "
            "to names the shadow no longer defines. Belt-and-braces catch.",
            border_style="yellow",
        )
    )
    return 2


def _finding_table(findings: list[FindingRef]) -> Table:
    table = Table(show_header=True, header_style="bold", box=None, pad_edge=False)
    table.add_column("check_id", style="cyan")
    table.add_column("severity")
    table.add_column("file")
    table.add_column("line", justify="right")
    table.add_column("message")
    for f in findings:
        table.add_row(
            f.check_id,
            f.severity,
            f.file_path or "-",
            str(f.line_number) if f.line_number is not None else "-",
            f.message,
        )
    return table


def _symbol_list(refs: list[SymbolRef]) -> str:
    return "\n".join(f"    [dim]{r.kind:<18}[/dim] {r.symbol_path}" for r in refs)


__all__ = ["smell_test_command"]
