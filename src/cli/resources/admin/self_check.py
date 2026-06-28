# src/cli/resources/admin/self_check.py

"""``core-admin admin self-check`` — manual preflight against the same
``cli_gate`` engine the autonomous audit uses.

The command audits the live Typer command registry against the eight
``cli.*`` rules wired to ``engine: cli_gate`` in
``.intent/enforcement/mappings/cli/interface_design.yaml`` (plus
``cli.command.no_duplicates`` in ``infrastructure/cli_commands.yaml``).
Findings are produced by the canonical ``CliCheck`` implementations and
match what ``core-admin code audit`` produces for the same rules.

``--write`` invokes ``MetadataScribeService`` to autonomously assign
``@command_meta`` decorators to commands that lack explicit metadata.
That branch is independent of the audit and uses ``walk_typer_app``
directly for command discovery.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer
from rich.console import Console

from body.atomic.executor import ActionExecutor
from cli.utils import core_command
from shared.cli.command_meta import (
    CommandBehavior,
    CommandExposure,
    CommandLayer,
    command_meta,
)
from shared.models import AuditFinding

from .hub import app


console = Console()


_CLI_GATE_RULE_IDS: tuple[str, ...] = (
    "cli.resource_first",
    "cli.no_layer_exposure",
    "cli.standard_verbs",
    "cli.dangerous_explicit",
    "cli.async_execution",
    "cli.discovery_strict",
    "cli.help_required",
    "cli.command.no_duplicates",
)


@app.command("self-check")
@command_meta(
    canonical_name="admin.self-check",
    behavior=CommandBehavior.VALIDATE,
    layer=CommandLayer.BODY,
    exposure=CommandExposure.GOVERNOR_ONLY,
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
    from cli.admin_cli import app as main_app
    from mind.governance.enforcement_loader import EnforcementMappingLoader
    from mind.logic.engines.registry import EngineRegistry
    from shared.cli.app_introspection import walk_typer_app
    from shared.infrastructure.intent.intent_repository import get_intent_repository
    from will.maintenance.metadata_scribe_service import MetadataScribeService

    core_context = ctx.obj

    commands = walk_typer_app(main_app, include_missing_handlers=True)
    unassigned = [c for c in commands if not c.get("has_explicit_meta")]

    if write:
        scribe = MetadataScribeService(core_context.cognitive_service)
        executor = ActionExecutor(core_context)
        if not unassigned:
            console.print(
                "[green]✅ All commands have explicit metadata. Nothing to scribe.[/green]"
            )
            return
        console.print(
            f"[bold cyan]🖋️  Metascribe: Analyzing {len(unassigned)} unassigned commands...[/bold cyan]\n"
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
                console.print(
                    f"   → Proposed for [yellow]{cmd['name']}[/yellow]: {meta_draft['canonical_name']}"
                )
                decorator = (
                    f'@command_meta(\n    canonical_name="{meta_draft["canonical_name"]}",\n'
                    f"    behavior=CommandBehavior.{meta_draft['behavior'].upper()},\n"
                    f"    layer=CommandLayer.{meta_draft['layer'].upper()},\n"
                    f'    summary="{meta_draft["summary"]}",\n'
                    f"    dangerous={meta_draft['dangerous']}\n)\n"
                )
                target_def = f"def {cmd['entrypoint']}"
                if f"async def {cmd['entrypoint']}" in source:
                    target_def = f"async def {cmd['entrypoint']}"
                new_source = source.replace(target_def, f"{decorator}{target_def}")
                rel_path = str(f_path.relative_to(core_context.git_service.repo_path))
                await executor.execute(
                    "file.edit", write=True, file_path=rel_path, code=new_source
                )
        return

    repo = get_intent_repository()
    repo.initialize()
    loader = EnforcementMappingLoader(intent_root=repo.root)
    cli_gate_engine = EngineRegistry.get("cli_gate")

    findings_by_rule: dict[str, list[AuditFinding]] = {}
    skipped: list[str] = []
    for rule_id in _CLI_GATE_RULE_IDS:
        strategy = loader.get_enforcement_strategy(rule_id)
        if not strategy or strategy.get("engine") != "cli_gate":
            skipped.append(rule_id)
            continue
        params: dict[str, Any] = dict(strategy.get("params", {}))
        findings = await cli_gate_engine.verify_context(
            core_context.auditor_context, params
        )
        if findings:
            findings_by_rule[rule_id] = findings

    total_findings = sum(len(v) for v in findings_by_rule.values())

    console.print("\n[bold cyan]🔍 CLI Registry Audit Results[/bold cyan]\n")

    if findings_by_rule:
        console.print("[bold red]❌ CONSTITUTIONAL VIOLATIONS:[/bold red]")
        for rule_id, findings in findings_by_rule.items():
            console.print(f"  [bold]{rule_id}[/bold] — {len(findings)} finding(s)")
            for finding in findings:
                item = finding.context.get("command_name") or finding.file_path or "?"
                console.print(f"    • {finding.message} ([dim]{item}[/dim])")
        console.print("")

    if skipped:
        console.print(f"[yellow]⚠️  Unmapped (skipped): {', '.join(skipped)}[/yellow]\n")

    console.print(f"  Total commands:            [bold]{len(commands)}[/bold]")
    console.print(f"  Total findings:            [bold]{total_findings}[/bold]")
    console.print(
        f"  Missing explicit @meta:    [bold yellow]{len(unassigned)}[/bold yellow]"
    )
    if unassigned:
        console.print(
            "\n[yellow]💡 Run with --write to autonomously assign metadata via AI.[/yellow]"
        )

    if not findings_by_rule and not skipped:
        console.print(
            "\n[bold green]✅ CLI Registry is healthy and aligned.[/bold green]"
        )
