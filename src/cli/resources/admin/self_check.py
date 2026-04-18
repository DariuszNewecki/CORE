# src/cli/resources/admin/self_check.py
from shared.logger import getLogger


logger = getLogger(__name__)
from pathlib import Path

import typer
from rich.console import Console

from body.atomic.executor import ActionExecutor
from cli.utils import core_command
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
# ID: 6fa9d0bd-63d7-4d93-a326-d0ee95793423
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
    verb_rule = repo.get_rule("cli.standard_verbs").content
    allowed = set(verb_rule.get("check", {}).get("params", {}).get("allowed_verbs", []))
    layer_rule = repo.get_rule("cli.no_layer_exposure").content
    forbidden = set(
        layer_rule.get("check", {}).get("params", {}).get("forbidden_resources", [])
    )
    report = audit_cli_registry(
        main_app, allowed_verbs=allowed, forbidden_resources=forbidden
    )
    unassigned = [c for c in report["commands"] if not c.get("has_explicit_meta")]
    if write:
        scribe = MetadataScribeService(core_context.cognitive_service)
        executor = ActionExecutor(core_context)
        if not unassigned:
            logger.info(
                "[green]✅ All commands have explicit metadata. Nothing to scribe.[/green]"
            )
        else:
            logger.info(
                "[bold cyan]🖋️  Metascribe: Analyzing %s unassigned commands...[/bold cyan]\n",
                len(unassigned),
            )
            for cmd in unassigned:
                f_path = Path(cmd["file_path"])
                if not f_path.exists():
                    continue
                source = f_path.read_text(encoding="utf-8")
                meta_draft = await scribe.draft_metadata(
                    function_name=cmd["entrypoint"],
                    docstring=cmd["summary"] or "",
                    file_path=cmd["file_path"],
                    source_code=source,
                )
                if meta_draft:
                    logger.info(
                        "   → Proposed for [yellow]%s[/yellow]: %s",
                        cmd["name"],
                        meta_draft["canonical_name"],
                    )
                    decorator = f'@command_meta(\n    canonical_name="{meta_draft["canonical_name"]}",\n    behavior=CommandBehavior.{meta_draft["behavior"].upper()},\n    layer=CommandLayer.{meta_draft["layer"].upper()},\n    summary="{meta_draft["summary"]}",\n    dangerous={meta_draft["dangerous"]}\n)\n'
                    target_def = f"def {cmd['entrypoint']}"
                    if f"async def {cmd['entrypoint']}" in source:
                        target_def = f"async def {cmd['entrypoint']}"
                    new_source = source.replace(target_def, f"{decorator}{target_def}")
                    rel_path = str(
                        f_path.relative_to(core_context.git_service.repo_path)
                    )
                    await executor.execute(
                        "file.edit", write=True, file_path=rel_path, code=new_source
                    )
    if not write:
        logger.info("\n[bold cyan]🔍 CLI Registry Audit Results[/bold cyan]\n")
        if report["violations"]:
            logger.info("[bold red]❌ CONSTITUTIONAL VIOLATIONS:[/bold red]")
            for v in report["violations"]:
                logger.info("   • %s ([dim]%s[/dim])", v["message"], v["item"])
            logger.info("")
        logger.info(
            "  Total commands:            [bold]%s[/bold]", report["total_commands"]
        )
        logger.info(
            "  Missing explicit @meta:    [bold yellow]%s[/bold yellow]",
            len(unassigned),
        )
        if unassigned:
            logger.info(
                "\n[yellow]💡 Run with --write to autonomously assign metadata via AI.[/yellow]"
            )
    if report["is_healthy"]:
        logger.info(
            "\n[bold green]✅ CLI Registry is healthy and aligned.[/bold green]"
        )
