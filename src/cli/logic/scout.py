# src/cli/logic/scout.py

"""
BYOR Scout — Phase B rule induction (ADR-119 D2/D3/D5/D7).

`core-admin project scout <target> [--write]` samples the target repo's source
code, calls ScoutInducer (Mind) to produce governance observations, matches each
observation to an enforcement mechanism via the catalog, walks the operator
through per-rule ratification (D5 — no --accept-all), and writes the confirmed
set to:
  <target>/.intent/rules/scout_inducted.json
  <target>/.intent/enforcement/mappings/scout.yaml

Observation and enforcement are separate concerns:
- The LLM observes what the repo's patterns suggest should be governed.
- CORE maps each observation to an engine + params via the enforcement catalog.
- The human ratifies both the governance intent and the proposed enforcement.

LLM-unavailable fallback (D7): when no cognitive_service is reachable, presents
the four universal rules from examples/starter-intent/ as the candidate menu.
Per-rule ratification still applies. Fallback candidates also go through catalog
matching for consistency.

CONSTITUTIONAL NOTES:
- Mind is imported lazily (inside the function body) to keep the layer boundary
  explicit — analogous to gap_analysis_service.py importing GRCApplicabilityGate.
- File writes route through file.create (ActionExecutor), the same sanctioned
  surface byor.py uses. Target dirs are addressed via CORE-root-relative paths.
- No writes to /tmp. Parent dirs in the external repo are created via
  context.file_handler.ensure_dir before the file.create call.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer
import yaml
from rich.console import Console
from rich.prompt import Prompt
from rich.rule import Rule

from body.atomic.executor import ActionExecutor
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.context import CoreContext


logger = getLogger(__name__)
console = Console()

# Detect-phase bounds — ADR-119 D3 "detect" step
_DETECT_MAX_FILES = 12
_DETECT_PER_FILE_CHARS = 3_000
_DETECT_ENTRY_NAMES = frozenset(
    {
        "__main__.py",
        "main.py",
        "app.py",
        "cli.py",
        "server.py",
        "run.py",
        "manage.py",
        "wsgi.py",
        "asgi.py",
    }
)

# Fallback source — ADR-119 D7
_FALLBACK_RULES_REL = ("examples", "starter-intent", ".intent", "rules", "starter.json")

# Enforcement catalog — maps governance intents to engine + params
_CATALOG_REL = ("var", "prompts", "scout_rule_inducer", "enforcement_catalog.yaml")

# Output paths relative to <target>/.intent/
_RULES_OUTPUT = "rules/scout_inducted.json"
_MAPPINGS_OUTPUT = "enforcement/mappings/scout.yaml"

# Valid enforcement levels
_ENFORCEMENT_LEVELS = ("blocking", "reporting", "advisory")


# ID: 349e00c4-ecf4-471a-969d-157161c8d3e0
async def induce_rules(
    context: CoreContext,
    path: Path,
    dry_run: bool = True,
) -> None:
    """Run Scout Phase B: detect → suggest → match → confirm → write.

    Requires that Phase A (project onboard) has already delivered the machinery
    floor into <path>/.intent/. Refuses if .intent/ is absent.
    """
    target_root = Path(path).resolve()
    core_root = context.git_service.repo_path.resolve()
    target_intent = target_root / ".intent"

    if not target_intent.exists():
        logger.error(
            "No .intent/ found at %s. Run `project onboard <target> --write` first (Phase A).",
            target_intent,
        )
        raise typer.Exit(code=1)

    if (target_intent / "rules" / "scout_inducted.json").exists():
        logger.error(
            "Scout-inducted rules already exist at %s. Remove them before re-running Scout.",
            target_intent / "rules" / "scout_inducted.json",
        )
        raise typer.Exit(code=1)

    # ── Detect ────────────────────────────────────────────────────────────────
    console.print(Rule("[bold cyan]Scout — Phase B: Rule Induction[/bold cyan]"))
    console.print("[cyan]Detect[/cyan] — sampling repository source files...")
    signals, sample_text = _detect_repo_signals(target_root)
    code_signals = _format_signals(signals, sample_text)

    # ── Suggest ───────────────────────────────────────────────────────────────
    candidates: list[dict[str, Any]] = []

    cognitive_service = getattr(context, "cognitive_service", None)
    if cognitive_service is None:
        try:
            cognitive_service = await context.registry.get_cognitive_service()
        except Exception as e:
            logger.info(
                "LLM service unavailable (%s) — will present universal menu.", e
            )

    if cognitive_service is not None:
        console.print("[cyan]Suggest[/cyan] — observing repository patterns via LLM...")
        try:
            client = await cognitive_service.aget_client_for_role(
                "ConstitutionalCoherenceAnalyst"
            )
            from mind.logic.scout_inducer import ScoutInducer  # lazy — see module note

            inducer = ScoutInducer(llm_client=client)
            candidates = await inducer.propose(code_signals=code_signals)
        except Exception as e:
            logger.warning(
                "LLM induction failed (%s) — falling back to universal menu.", e
            )

    if not candidates:
        console.print(
            "[yellow]⚠  LLM unavailable or no candidates returned — "
            "presenting universal rule menu (ADR-119 D7).[/yellow]"
        )
        candidates = _load_fallback_candidates(core_root)

    if not candidates:
        console.print("[red]No candidate rules available. Nothing to ratify.[/red]")
        raise typer.Exit(code=1)

    # ── Match observations to enforcement ─────────────────────────────────────
    console.print("[cyan]Match[/cyan] — mapping observations to enforcement catalog...")
    catalog = _load_enforcement_catalog(core_root)
    candidates = [_match_enforcement(c, catalog) for c in candidates]

    matched = sum(1 for c in candidates if c.get("enforcement_matched"))
    unmatched = len(candidates) - matched
    if unmatched:
        console.print(
            f"[yellow]  {matched} matched · {unmatched} unmatched "
            f"(will be declared-only, not enforced)[/yellow]"
        )

    # ── Confirm (ADR-119 D5 — mandatory; no --accept-all) ────────────────────
    console.print(
        f"\n[bold]Confirm[/bold] — {len(candidates)} candidate rule(s) to review:\n"
    )
    confirmed = _run_confirm_loop(candidates)

    if not confirmed:
        console.print("\n[yellow]No rules confirmed. Nothing written.[/yellow]")
        return

    # ── Write ─────────────────────────────────────────────────────────────────
    write = not dry_run
    rel_base = os.path.relpath(target_root, core_root)
    executor = ActionExecutor(context)

    rules_json = _build_rules_document(confirmed)
    mappings_yaml = _build_mappings_document(confirmed)

    for output_rel, content in (
        (_RULES_OUTPUT, rules_json),
        (_MAPPINGS_OUTPUT, mappings_yaml),
    ):
        await _write_intent_file(
            context=context,
            executor=executor,
            rel_base=rel_base,
            output_rel=output_rel,
            content=content,
            write=write,
        )

    enforced = sum(1 for c in confirmed if c.get("enforcement_matched"))
    declared_only = len(confirmed) - enforced

    if not write:
        console.print(
            f"\n[yellow]Dry run — {len(confirmed)} rule(s) would be written to "
            f"{target_intent} ({enforced} enforced, {declared_only} declared-only). "
            f"Pass --write to apply.[/yellow]"
        )
    else:
        console.print(
            f"\n[green]✅ {len(confirmed)} rule(s) written to {target_intent} "
            f"({enforced} enforced, {declared_only} declared-only)[/green]"
        )
        console.print(
            "Next: run `core-admin code audit --offline` against this repo to enforce them."
        )


# ── Detect helpers ─────────────────────────────────────────────────────────────


def _detect_repo_signals(
    target_root: Path,
) -> tuple[dict[str, Any], str]:
    """Sample Python files and extract structural signals from the target repo."""
    all_py = sorted(target_root.rglob("*.py"))

    # Prioritise: entry points → test files → largest files
    entry = [p for p in all_py if p.name in _DETECT_ENTRY_NAMES]
    test_files = [
        p
        for p in all_py
        if p not in entry
        and (p.name.startswith("test_") or p.name.endswith("_test.py"))
    ]
    others = sorted(
        [p for p in all_py if p not in entry and p not in test_files],
        key=lambda p: p.stat().st_size,
        reverse=True,
    )
    sampled = (entry + others + test_files)[:_DETECT_MAX_FILES]

    # Read excerpts
    excerpts: list[tuple[str, str]] = []
    for p in sampled:
        try:
            text = p.read_text(encoding="utf-8", errors="replace")[
                :_DETECT_PER_FILE_CHARS
            ]
            rel = str(p.relative_to(target_root))
            excerpts.append((rel, text))
        except OSError:
            pass

    combined = "\n".join(t for _, t in excerpts)

    # Structural signals
    has_src = (target_root / "src").is_dir()
    has_tests = bool(
        (target_root / "tests").is_dir()
        or (target_root / "test").is_dir()
        or test_files
    )

    def _count(pattern: str) -> int:
        return len(re.findall(pattern, combined, re.MULTILINE))

    def_count = _count(r"^\s*(?:async\s+)?def\s+[A-Za-z]")
    class_count = _count(r"^\s*class\s+[A-Za-z]")
    public_count = def_count + class_count
    docstring_after = _count(r'(?:def|class)[^\n]+\n\s+"""')
    id_anchors = _count(r"#\s*ID\s*:")
    print_calls = _count(r"\bprint\s*\(")
    bare_except = _count(
        r"except\s*(?:Exception\s*|BaseException\s*)?:\s*(?:pass\s*)?$"
    )
    future_annotations = _count(r"from __future__ import annotations")
    type_annotations = _count(r"\)\s*->")
    decorator_usage = _count(r"^\s*@\w")

    signals: dict[str, Any] = {
        "total_py_files": len(all_py),
        "sampled_files": len(sampled),
        "has_src_layout": has_src,
        "has_tests": has_tests,
        "public_symbols_estimate": public_count,
        "docstrings_present_estimate": docstring_after,
        "id_anchors_found": id_anchors,
        "print_calls": print_calls,
        "bare_except_occurrences": bare_except,
        "future_annotations_files": future_annotations,
        "type_annotations_present": type_annotations > 0,
        "decorator_usage": decorator_usage > 0,
    }
    return signals, "\n\n".join(f"--- {rel} ---\n{text}" for rel, text in excerpts)


def _format_signals(signals: dict[str, Any], sample_text: str) -> str:
    """Format structural signals as a string for the LLM prompt."""
    pub = signals["public_symbols_estimate"]
    doc = signals["docstrings_present_estimate"]
    doc_pct = f"~{int(doc / pub * 100)}%" if pub else "n/a"

    return (
        f"Python files total: {signals['total_py_files']}\n"
        f"Files sampled: {signals['sampled_files']}\n"
        f"Has src/ layout: {'yes' if signals['has_src_layout'] else 'no'}\n"
        f"Has tests directory: {'yes' if signals['has_tests'] else 'no'}\n"
        f"Public symbols (estimate from sample): {pub}\n"
        f"  — with docstrings: {doc_pct}\n"
        f"print() calls found: {signals['print_calls']}\n"
        f"Bare except occurrences: {signals['bare_except_occurrences']}\n"
        f"Type annotations (->): {'present' if signals['type_annotations_present'] else 'absent'}\n"
        f"from __future__ import annotations: "
        f"{signals['future_annotations_files']} sampled files\n"
        f"Decorator usage: {'yes' if signals['decorator_usage'] else 'no'}\n"
        f"\nCODE SAMPLES\n{sample_text}"
    )


# ── Enforcement catalog (ADR-119 separation of observation from enforcement) ────


def _load_enforcement_catalog(core_root: Path) -> list[dict[str, Any]]:
    """Load the Scout enforcement catalog.

    Maps governance intent labels to engine + params. Kept separate from the
    LLM prompt so the vocabulary can grow without prompt changes.
    """
    catalog_path = core_root.joinpath(*_CATALOG_REL)
    if not catalog_path.exists():
        logger.warning("Scout enforcement catalog not found at %s", catalog_path)
        return []
    try:
        doc = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
        return doc.get("entries", []) if isinstance(doc, dict) else []
    except Exception as e:
        logger.warning("Could not load enforcement catalog: %s", e)
        return []


def _match_enforcement(
    candidate: dict[str, Any],
    catalog: list[dict[str, Any]],
) -> dict[str, Any]:
    """Match a candidate's rule_id to a catalog entry.

    Strips the 'scout.' prefix, then tries:
    1. Exact match against the catalog entry's 'id' field.
    2. Substring match against the entry's 'match_keys'.

    Augments the candidate with engine/params/scope on match and sets
    'enforcement_matched'. Unmatched candidates are declared-only (rules.json
    only, no enforcement mapping).
    """
    rule_id = candidate.get("rule_id", "")
    bare = rule_id.split(".", 1)[-1] if "." in rule_id else rule_id

    for entry in catalog:
        if bare == entry.get("id", ""):
            return _augment(candidate, entry)
        for key in entry.get("match_keys", []):
            if key in bare or bare in key:
                return _augment(candidate, entry)

    return {**candidate, "enforcement_matched": False}


def _augment(candidate: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    """Merge catalog enforcement details into a candidate observation."""
    return {
        **candidate,
        "engine": entry["engine"],
        "params": entry.get("params", {}),
        "scope": entry.get(
            "scope_default", {"applies_to": ["**/*.py"], "excludes": []}
        ),
        "enforcement_matched": True,
    }


# ── Fallback helpers (ADR-119 D7) ─────────────────────────────────────────────


def _load_fallback_candidates(core_root: Path) -> list[dict[str, Any]]:
    """Load the starter rules as fallback candidates.

    Produces observation-only candidates (no engine/params) — they go through
    catalog matching in induce_rules() like LLM-produced candidates.
    """
    rules_path = core_root.joinpath(*_FALLBACK_RULES_REL)
    if not rules_path.exists():
        logger.warning("Fallback starter-intent not found at %s", core_root)
        return []

    try:
        rules_doc = json.loads(rules_path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("Could not load fallback candidates: %s", e)
        return []

    candidates: list[dict[str, Any]] = []
    for rule in rules_doc.get("rules", []):
        old_id: str = rule.get("id", "")
        new_id = (
            "scout." + old_id.split(".", 1)[-1] if "." in old_id else f"scout.{old_id}"
        )
        candidates.append(
            {
                "rule_id": new_id,
                "statement": rule.get("statement", ""),
                "enforcement": rule.get("enforcement", "reporting"),
                "rationale": rule.get("rationale")
                or "(universal rule — LLM fallback menu)",
                "evidence_sample": "",
                "ramp_note": "",
            }
        )
    return candidates


# ── Confirm loop (ADR-119 D5) ─────────────────────────────────────────────────


def _run_confirm_loop(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Walk the operator through per-rule ratification.

    ADR-119 D5: no batch-accept path. Every candidate is reviewed individually.
    The operator may accept, reject, or change the enforcement level for each.
    """
    confirmed: list[dict[str, Any]] = []
    total = len(candidates)

    for idx, candidate in enumerate(candidates, start=1):
        console.print(Rule(f"Rule {idx} / {total}"))
        _display_candidate(candidate)

        try:
            choice = Prompt.ask(
                "[bold]Action[/bold]",
                choices=["a", "r", "c"],
                default="a",
                show_choices=True,
                show_default=True,
            ).lower()
        except (EOFError, KeyboardInterrupt):
            console.print(
                "\n[yellow]Confirmation interrupted — no further rules reviewed.[/yellow]"
            )
            break

        if choice == "r":
            console.print("[dim]  ↳ Rejected.[/dim]")
            continue

        if choice == "c":
            try:
                new_level = Prompt.ask(
                    "  New enforcement level",
                    choices=list(_ENFORCEMENT_LEVELS),
                    default=candidate.get("enforcement", "reporting"),
                ).lower()
            except (EOFError, KeyboardInterrupt):
                console.print(
                    "\n[yellow]Level change interrupted — rule rejected.[/yellow]"
                )
                continue
            candidate = {**candidate, "enforcement": new_level}

        console.print(f"[green]  ↳ Accepted ({candidate['enforcement']}).[/green]")
        confirmed.append(candidate)

    return confirmed


def _display_candidate(candidate: dict[str, Any]) -> None:
    """Render a single candidate rule for operator review.

    Shows observation and enforcement as distinct sections so the operator
    can evaluate each independently.
    """
    rule_id = candidate.get("rule_id", "<unknown>")
    statement = candidate.get("statement", "")
    enforcement = candidate.get("enforcement", "reporting")
    rationale = candidate.get("rationale", "")
    evidence = candidate.get("evidence_sample", "")
    ramp = candidate.get("ramp_note", "")
    matched = candidate.get("enforcement_matched", False)

    color = {"blocking": "red", "reporting": "yellow", "advisory": "dim"}.get(
        enforcement, "white"
    )

    console.print("  [bold underline]OBSERVATION[/bold underline]")
    console.print(f"  [bold]ID:[/bold]          {rule_id}")
    console.print(f"  [bold]Statement:[/bold]   {statement}")
    console.print(f"  [bold]Enforcement:[/bold] [{color}]{enforcement}[/{color}]")
    console.print(f"  [bold]Rationale:[/bold]   {rationale}")
    if evidence:
        console.print(f"  [bold]Evidence:[/bold]    {evidence}")
    if ramp:
        console.print(f"  [bold]Ramp note:[/bold]   [yellow]{ramp}[/yellow]")

    console.print()
    console.print("  [bold underline]ENFORCEMENT[/bold underline]")
    if matched:
        engine = candidate.get("engine", "")
        params = candidate.get("params", {})
        scope = candidate.get("scope", {})
        applies = scope.get("applies_to", [])
        excludes = scope.get("excludes", [])
        console.print(
            f"  [bold]Engine:[/bold]      {engine} {json.dumps(params, separators=(',', ':'))}"
        )
        console.print(f"  [bold]Scope:[/bold]       applies_to {applies}")
        if excludes:
            console.print(f"               excludes   {excludes}")
    else:
        console.print(
            "  [yellow]⚠  No catalog match — rule will be declared but not enforced.[/yellow]"
        )
        console.print(
            "  [dim]To enforce it, add an entry to "
            "var/prompts/scout_rule_inducer/enforcement_catalog.yaml[/dim]"
        )

    console.print()
    console.print("  [dim]a = accept · r = reject · c = change enforcement level[/dim]")


# ── Output builders ────────────────────────────────────────────────────────────


def _build_rules_document(confirmed: list[dict[str, Any]]) -> str:
    """Produce the rules/scout_inducted.json content from confirmed candidates."""
    rules = [
        {
            "id": c["rule_id"],
            "statement": c["statement"],
            "authority": "policy",
            "phase": "runtime",
            "enforcement": c["enforcement"],
            "rationale": c.get("rationale", ""),
        }
        for c in confirmed
    ]
    doc = {
        "$schema": "META/rule_document.schema.json",
        "kind": "rule_document",
        "metadata": {
            "id": "rules.scout_inducted",
            "title": "Scout-Inducted Rules",
            "version": "1.0.0",
            "authority": "policy",
            "phase": "runtime",
            "status": "active",
        },
        "rules": rules,
    }
    return json.dumps(doc, indent=2)


def _build_mappings_document(confirmed: list[dict[str, Any]]) -> str:
    """Produce the enforcement/mappings/scout.yaml content from confirmed candidates.

    Unmatched candidates (enforcement_matched=False) are omitted — they are
    declared in rules/scout_inducted.json as declared-only rules with no engine.
    """
    mappings: dict[str, Any] = {}
    for c in confirmed:
        if not c.get("enforcement_matched"):
            continue
        scope = c.get("scope", {})
        entry: dict[str, Any] = {
            "engine": c.get("engine", "ast_gate"),
            "params": c.get("params", {}),
            "scope": {
                "applies_to": scope.get("applies_to", ["**/*.py"]),
            },
        }
        excludes = scope.get("excludes", [])
        if excludes:
            entry["scope"]["excludes"] = excludes
        mappings[c["rule_id"]] = entry

    return yaml.dump({"mappings": mappings}, default_flow_style=False, sort_keys=False)


# ── Write helper ───────────────────────────────────────────────────────────────


async def _write_intent_file(
    context: CoreContext,
    executor: ActionExecutor,
    rel_base: str,
    output_rel: str,
    content: str,
    write: bool,
) -> None:
    """Write one file into <target>/.intent/ via the file.create atomic action."""
    file_path = (Path(rel_base) / ".intent" / output_rel).as_posix()
    parent_rel = str(Path(file_path).parent)

    if write:
        context.file_handler.ensure_dir(parent_rel)
    else:
        logger.info("   -> [DRY RUN] would ensure dir %s", parent_rel)

    await executor.execute(
        action_id="file.create",
        write=write,
        file_path=file_path,
        code=content,
    )

    if write:
        core_root = context.git_service.repo_path.resolve()
        dest = core_root / file_path
        if dest.is_file():
            logger.info("   -> ✅ %s", file_path)
        else:
            logger.error("   -> ❌ not written: %s", file_path)
    else:
        logger.info("   -> [DRY RUN] would write %s", file_path)
