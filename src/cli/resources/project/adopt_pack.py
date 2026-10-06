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
from shared.config import settings
from shared.infrastructure.bundled_packs import pack_registry_dir
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
    remove the need to author governance YAML manually. Packs are resolved from
    the repository's packs/ registry when it has one (a CORE source checkout),
    otherwise from the registry bundled with the installed core-runtime.

    The target must already carry CORE's machinery floor (.intent/META and the
    rest, delivered by `project new` or `project onboard`); without it the
    command refuses.

    Run without --write to preview what would be written. Run with --write
    to apply. After adoption, run 'core-admin code audit --offline' to see
    findings against the pack's rules.
    """
    with pack_registry_dir(settings.MIND.parent) as packs_dir:
        loader = PackLoader(packs_dir)
        pack = loader.load_pack(pack_id)
        available = loader.list_pack_ids() if pack is None else []
    if pack is None:
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

    # A pack is law, not machinery. Without the machinery floor (.intent/META
    # and the rest) the audit cannot load the target at all (#939), so the
    # pack would be rules nothing enforces: refuse instead of delivering them.
    if not (intent_dir / "META").is_dir():
        console.print(
            f"[bold red]{target_dir} has no machinery floor[/bold red] "
            "(.intent/META is missing), so CORE could not audit it.\n"
            "Deliver the floor first: [cyan]core-admin project new <name> --write"
            "[/cyan] for a new repository, or [cyan]core project onboard <path> "
            "--write[/cyan] (core-cli, needs a running CORE API) for an existing one."
        )
        raise typer.Exit(1)

    # Two rule documents declaring the same rule ID stop the audit (the
    # repository refuses duplicates), e.g. python-hygiene contains the
    # starter's rules. Refuse before writing; re-adopting this pack replaces
    # its own file, so that file does not count.
    pack_ids = {r.get("id") for r in pack.rules if r.get("id")}
    taken = {
        rid: path
        for rid, path in _declared_rule_ids(
            intent_dir / "rules", skip=rules_file
        ).items()
        if rid in pack_ids
    }
    if taken:
        console.print(
            f"[bold red]{pack_id!r} declares rule IDs this repository already "
            f"has[/bold red] — adopting it would stop the audit with a duplicate "
            "rule error:"
        )
        for rid, path in sorted(taken.items()):
            console.print(f"  {rid}  (in {path.relative_to(target_dir)})")
        console.print(
            "Remove the conflicting rules (or the pack that brought them) first."
        )
        raise typer.Exit(1)

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
    from cli.logic.byor import core_source_root, deliver_external_intent_files

    core_root = core_source_root()

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

    # ADR-169 D5: the pack's out-of-repo writes are recorded, even if the
    # delivery stops part-way.
    from body.services.outside_write_ledger import OutsideWriteLog

    outside = OutsideWriteLog(target_dir, produced_by="project.adopt_pack")
    await outside.require_ledger()  # no ledger, no write (#953)
    try:
        deliver_external_intent_files(target_dir, core_root, files, outside)
    finally:
        await outside.flush()
    if tree_update is not None:
        console.print(f"  Updated {tree_yaml.name}: packs: section")

    console.print(
        "\n[bold green]Pack applied.[/bold green] "
        "Run 'core-admin code audit --offline' to see findings."
    )


_RULE_SECTIONS = ("rules", "safety_rules", "agent_rules", "principles")


def _declared_rule_ids(rules_dir: Path, skip: Path) -> dict[str, Path]:
    """Rule IDs declared by the rule documents under ``rules_dir``.

    Reads the same files and sections the intent repository indexes (YAML or
    JSON; ``rules`` and its sibling sections, as a list or an id-keyed map),
    ignoring ``skip`` and unreadable files.
    """
    import yaml as _yaml

    declared: dict[str, Path] = {}
    if not rules_dir.is_dir():
        return declared
    for pattern in ("*.yaml", "*.yml", "*.json"):
        for path in sorted(rules_dir.rglob(pattern)):
            if path == skip:
                continue
            try:
                text = path.read_text(encoding="utf-8")
                data = (
                    json.loads(text)
                    if path.suffix == ".json"
                    else _yaml.safe_load(text)
                )
            except (OSError, ValueError, _yaml.YAMLError):
                continue
            if not isinstance(data, dict) or data.get("kind") == "governance_pack":
                continue
            for section in _RULE_SECTIONS:
                rules = data.get(section)
                if isinstance(rules, dict):
                    ids = [k for k, v in rules.items() if isinstance(v, dict)]
                elif isinstance(rules, list):
                    ids = [
                        r.get("id") or r.get("rule_id")
                        for r in rules
                        if isinstance(r, dict)
                    ]
                else:
                    continue
                for rid in ids:
                    if isinstance(rid, str) and rid.strip():
                        declared.setdefault(rid, path)
    return declared


def _upsert_pack_in_tree(
    tree_yaml: Path,
    pack_id: str,
    overrides: dict[str, str],
) -> str | None:
    """Return intent_tree.yaml text with the pack upserted in ``packs:``, or None.

    None means the target has a ``META/`` directory but no ``intent_tree.yaml``
    in it. The offline audit discovers ``rules/packs/`` directly, so this is a
    warning, not a refusal (a target with no ``META/`` at all is refused
    before this point).
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
