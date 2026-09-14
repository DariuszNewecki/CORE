# src/cli/resources/project/adopt_pack.py

"""
`core project adopt-pack` — apply a governance pack to a target repo.

Dry-runs by default. With --write:
  1. Writes the pack's rule definitions to .intent/rules/packs/<slug>.json
  2. Writes the pack's enforcement mappings to
     .intent/enforcement/mappings/packs/<slug>.yaml
  3. Adds a `packs:` entry to the target's .intent/META/intent_tree.yaml

Per ADR-146 D2 this is a consumer command; it migrates to core-cli when
Item 3 of the External Adoption Plan is executed.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.console import Console
from rich.table import Table

from cli.utils import core_command
from shared.config import resolve_default_repo_path, settings
from shared.infrastructure.intent.pack_loader import PackLoader


if TYPE_CHECKING:
    pass

from . import app


console = Console()
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _pack_slug(pack_id: str) -> str:
    return _SLUG_RE.sub("_", pack_id.lower()).strip("_")


@app.command("adopt-pack")
@core_command(dangerous=True, requires_context=False)
# ID: 28d2160f-622b-4521-9d8e-84b268108b1b
async def adopt_pack_command(
    pack_id: str = typer.Argument(
        ...,
        help="Pack ID to adopt, e.g. core/starter-python",
    ),
    target_dir: Path = typer.Option(
        Path("."),
        "--target-dir",
        "-t",
        help="Root of the target repo. Defaults to CWD.",
        resolve_path=True,
    ),
    write: bool = typer.Option(
        False,
        "--write",
        help="Apply changes. Without --write, previews what would be written.",
    ),
    override: list[str] = typer.Option(
        [],
        "--override",
        help=(
            "Downgrade a rule's enforcement. Format: 'rule_id:enforcement', "
            "e.g. 'starter.no_bare_except:reporting'."
        ),
    ),
) -> None:
    """Apply a governance pack to a target repository.

    Packs are self-contained bundles of rules and enforcement mappings that
    remove the need to author governance YAML manually. Each pack is resolved
    from the installed core-runtime's top-level packs/ registry (a sibling of
    .intent/, not part of CORE's own law — ADR-149).

    Run without --write to preview what would be written. Run with --write
    to apply. After adoption, run 'core-admin code audit --offline' to see
    findings against the pack's rules.
    """
    builtin_packs_dir = settings.MIND.parent / "packs"
    loader = PackLoader(builtin_packs_dir)

    pack = loader.load_pack(pack_id)
    if pack is None:
        available = loader.list_pack_ids()
        console.print(f"[bold red]Pack not found:[/bold red] {pack_id!r}")
        if available:
            console.print(f"Available packs: {', '.join(available)}")
        raise typer.Exit(1)

    # Parse --override flags
    parsed_overrides: dict[str, str] = {}
    for ov in override:
        if ":" not in ov:
            console.print(
                f"[bold red]Invalid --override format:[/bold red] {ov!r} "
                "(expected 'rule_id:enforcement')"
            )
            raise typer.Exit(1)
        rule_id, enforcement = ov.split(":", 1)
        valid_levels = {"blocking", "reporting", "advisory"}
        if enforcement not in valid_levels:
            console.print(
                f"[bold red]Invalid enforcement level:[/bold red] {enforcement!r} "
                f"(allowed: {', '.join(sorted(valid_levels))})"
            )
            raise typer.Exit(1)
        parsed_overrides[rule_id.strip()] = enforcement.strip()

    # Resolve target paths
    intent_dir = target_dir / ".intent"
    rules_out = intent_dir / "rules" / "packs"
    mappings_out = intent_dir / "enforcement" / "mappings" / "packs"
    tree_yaml = intent_dir / "META" / "intent_tree.yaml"
    slug = _pack_slug(pack_id)
    rules_file = rules_out / f"{slug}.json"
    mappings_file = mappings_out / f"{slug}.yaml"

    # Build effective rules (apply overrides to enforcement level)
    effective_rules = []
    for rule in pack.rules:
        r = dict(rule)
        if r.get("id") in parsed_overrides:
            r["enforcement"] = parsed_overrides[r["id"]]
        effective_rules.append(r)

    # Preview table
    mode_label = (
        "[bold green]WRITE[/bold green]"
        if write
        else "[bold yellow]DRY-RUN[/bold yellow]"
    )
    console.print(f"\n[bold]adopt-pack[/bold] {pack_id!r}  {mode_label}")
    console.print(f"  Pack:    {pack.title} v{pack.version}  [{pack.level}]")
    console.print(f"  Target:  {intent_dir}")
    console.print()

    tbl = Table(show_header=True, header_style="bold cyan")
    tbl.add_column("Rule ID")
    tbl.add_column("Enforcement")
    tbl.add_column("Engine")
    for rule in effective_rules:
        rid = rule.get("id", "?")
        enforcement = rule.get("enforcement", "?")
        engine = (pack.enforcement_mappings.get(rid) or {}).get("engine", "?")
        override_marker = " *" if rid in parsed_overrides else ""
        tbl.add_row(f"{rid}{override_marker}", enforcement, engine)
    console.print(tbl)

    console.print()
    console.print(f"  Would write: {rules_file}")
    console.print(f"  Would write: {mappings_file}")
    console.print(f"  Would update: {tree_yaml}")

    if not write:
        console.print("\n[dim]Run with [bold]--write[/bold] to apply.[/dim]")
        return

    # --- Apply ---
    # External-target .intent/ delivery routes through the ADR-111 D3 lane in
    # cli.logic.byor: FileHandler is repo-bound and hard-blocks any literal
    # .intent/ path at the governed-artifact tier, so the pack files are
    # assembled here and written by the one module sanctioned for that write.
    from cli.logic.byor import deliver_external_intent_files

    core_root = resolve_default_repo_path()

    # 1. Rule document
    rule_doc = {
        "$schema": "META/rule_document.schema.json",
        "kind": "rule_document",
        "metadata": {
            "id": f"rules.packs.{slug}",
            "title": f"{pack.title} (pack)",
            "version": pack.version,
            "authority": "policy",
            "phase": "runtime",
            "status": "active",
        },
        "rules": effective_rules,
    }
    files: dict[str, str] = {
        rules_file.relative_to(target_dir).as_posix(): json.dumps(rule_doc, indent=4)
        + "\n",
    }

    # 2. Enforcement mappings
    import yaml as _yaml  # local import — CLI layer only

    # The mapping drives HOW, not WHAT enforcement; overrides live in the rule
    # doc. Dump the whole document so entries nest under ``mappings:`` — the
    # shape every mapping file under .intent/enforcement/mappings/ uses.
    files[mappings_file.relative_to(target_dir).as_posix()] = _yaml.dump(
        {"mappings": dict(pack.enforcement_mappings)},
        default_flow_style=False,
        sort_keys=False,
    )

    # 3. Update intent_tree.yaml packs: section (only if the target has one)
    tree_update = _upsert_pack_in_tree(tree_yaml, pack_id, parsed_overrides)
    if tree_update is not None:
        files[tree_yaml.relative_to(target_dir).as_posix()] = tree_update

    deliver_external_intent_files(target_dir, core_root, files)
    if tree_update is not None:
        console.print(f"  Updated {tree_yaml.name}: packs: section")

    console.print(
        "\n[bold green]Pack applied.[/bold green] "
        "Run 'core-admin code audit --offline' to see findings."
    )


def _upsert_pack_in_tree(
    tree_yaml: Path,
    pack_id: str,
    overrides: dict[str, str],
) -> str | None:
    """Return intent_tree.yaml text with the pack upserted in ``packs:``, or None.

    None means the target has no ``META/intent_tree.yaml`` (a bare repo that
    adopted a pack without the machinery floor). The pack still works — the
    offline audit discovers ``rules/packs/`` directly — so this is a warning,
    not a refusal.
    """
    if not tree_yaml.exists():
        console.print(
            f"[yellow]Warning:[/yellow] {tree_yaml} not found — skipping packs: update."
        )
        return None

    import yaml as _yaml

    data = _yaml.safe_load(tree_yaml.read_text("utf-8")) or {}
    packs: list[dict] = data.get("packs") or []

    # Remove existing entry for this pack_id (re-add below)
    packs = [p for p in packs if p.get("id") != pack_id]

    new_entry: dict = {"id": pack_id, "source": "local"}
    if overrides:
        new_entry["overrides"] = [
            {"rule_id": rid, "enforcement": enf} for rid, enf in overrides.items()
        ]
    packs.append(new_entry)
    data["packs"] = packs
    return _yaml.dump(data, default_flow_style=False, allow_unicode=True)
