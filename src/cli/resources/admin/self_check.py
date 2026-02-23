# src/cli/resources/admin/self_check.py
# ID: f7a1b2c3-d4e5-6789-abcd-ef0123456789

from pathlib import Path

import typer
from rich.console import Console

from body.atomic.executor import ActionExecutor
from shared.cli_utils import core_command
from shared.models.command_meta import CommandBehavior, CommandLayer, command_meta

from .hub import app


console = Console()


@app.command("self-check")
@command_meta(
    canonical_name="admin.self-check",
    behavior=CommandBehavior.VALIDATE,
    layer=CommandLayer.BODY,
    summary="Validate CLI command registration and constitutional alignment",
)
@core_command(dangerous=True, requires_context=True)
# ID: f7a1b2c3-d4e5-6789-abcd-ef0123456789
async def self_check_cmd(
    ctx: typer.Context,
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show full command listing."
    ),
    write: bool = typer.Option(
        False, "--write", help="Autonomously repair missing metadata using AI."
    ),
) -> None:
    """
    Validate CLI registry against structural and constitutional rules.
    Use --write to automatically assign missing @command_meta decorators.
    """
    from body.maintenance.command_sync_service import audit_cli_registry
    from cli.admin_cli import app as main_app
    from shared.infrastructure.intent.intent_repository import get_intent_repository
    from will.maintenance.metadata_scribe_service import MetadataScribeService

    core_context = ctx.obj
    repo = get_intent_repository()
    repo.initialize()

    # 1. Load the "Law" from the Mind
    verb_rule = repo.get_rule("cli.standard_verbs").content
    allowed = set(verb_rule.get("check", {}).get("params", {}).get("allowed_verbs", []))
    layer_rule = repo.get_rule("cli.no_layer_exposure").content
    forbidden = set(
        layer_rule.get("check", {}).get("params", {}).get("forbidden_resources", [])
    )

    # 2. Sensation: Audit the current state
    report = audit_cli_registry(
        main_app, allowed_verbs=allowed, forbidden_resources=forbidden
    )

    # Identify commands missing explicit metadata
    unassigned = [c for c in report["commands"] if not c.get("has_explicit_meta")]

    # 3. Reflexive Action: If --write is enabled, fix missing metadata
    if write:
        scribe = MetadataScribeService(core_context.cognitive_service)
        executor = ActionExecutor(core_context)

        if not unassigned:
            console.print(
                "[green]✅ All commands have explicit metadata. Nothing to scribe.[/green]"
            )
        else:
            console.print(
                f"[bold cyan]🖋️  Metascribe: Analyzing {len(unassigned)} unassigned commands...[/bold cyan]\n"
            )

            for cmd in unassigned:
                f_path = Path(cmd["file_path"])
                if not f_path.exists():
                    continue

                source = f_path.read_text(encoding="utf-8")

                # Will: AI Drafts the metadata
                meta_draft = await scribe.draft_metadata(
                    function_name=cmd["entrypoint"],
                    docstring=cmd["summary"] or "",
                    file_path=cmd["file_path"],
                    source_code=source,
                )

                if meta_draft:
                    console.print(
                        f"   → Proposed for [yellow]{cmd['name']}[/yellow]: {meta_draft['canonical_name']}"
                    )

                    # Construct the decorator string
                    decorator = f'@command_meta(\n    canonical_name="{meta_draft["canonical_name"]}",\n    behavior=CommandBehavior.{meta_draft["behavior"].upper()},\n    layer=CommandLayer.{meta_draft["layer"].upper()},\n    summary="{meta_draft["summary"]}",\n    dangerous={meta_draft["dangerous"]}\n)\n'

                    # Logic to insert decorator (Simple string replacement for this tool)
                    # We look for the function definition and insert above it
                    target_def = f"def {cmd['entrypoint']}"
                    if f"async def {cmd['entrypoint']}" in source:
                        target_def = f"async def {cmd['entrypoint']}"

                    new_source = source.replace(target_def, f"{decorator}{target_def}")

                    # Body: Use the Atomic Action Gateway to save the change
                    rel_path = str(
                        f_path.relative_to(core_context.git_service.repo_path)
                    )
                    await executor.execute(
                        "file.edit", write=True, file_path=rel_path, code=new_source
                    )

    # 4. Presentation
    if not write:
        console.print("\n[bold cyan]🔍 CLI Registry Audit Results[/bold cyan]\n")

        if report["violations"]:
            console.print("[bold red]❌ CONSTITUTIONAL VIOLATIONS:[/bold red]")
            for v in report["violations"]:
                console.print(f"   • {v['message']} ([dim]{v['item']}[/dim])")
            console.print("")

        console.print(
            f"  Total commands:            [bold]{report['total_commands']}[/bold]"
        )
        console.print(
            f"  Missing explicit @meta:    [bold yellow]{len(unassigned)}[/bold yellow]"
        )

        if unassigned:
            console.print(
                "\n[yellow]💡 Run with --write to autonomously assign metadata via AI.[/yellow]"
            )

    if report["is_healthy"]:
        console.print(
            "\n[bold green]✅ CLI Registry is healthy and aligned.[/bold green]"
        )
