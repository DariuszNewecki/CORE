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

import ast
import json
import os
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
    console.print(
        "[cyan]Detect[/cyan] — extracting structural signals from full repository..."
    )
    signals = _extract_repo_signals(target_root)
    code_signals = _format_signal_report(signals)

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

_SKIP_DIR_PARTS: frozenset[str] = frozenset(
    {".venv", "venv", "build", "dist", "__pycache__", "node_modules", ".git"}
)


def _should_include_file(p: Path, root: Path) -> bool:
    """Return True unless the file lives inside a directory we always skip."""
    try:
        rel = p.relative_to(root)
    except ValueError:
        return True
    return not any(part in _SKIP_DIR_PARTS for part in rel.parts)


def _get_decorator_name(node: ast.expr) -> str:
    """Extract the leaf identifier from a decorator node."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Call):
        return _get_decorator_name(node.func)
    return ""


def _has_docstring(
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
) -> bool:
    """Return True if the first statement in the body is a string constant."""
    return (
        bool(node.body)
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    )


def _extract_ci_signals(target_root: Path) -> dict[str, Any]:
    """Read mypy/ruff configuration from pyproject.toml, if present."""
    pyproject = target_root / "pyproject.toml"
    if not pyproject.exists():
        return {}
    try:
        import tomllib

        with pyproject.open("rb") as f:
            doc = tomllib.load(f)
        tool = doc.get("tool", {})
        result: dict[str, Any] = {}
        mypy = tool.get("mypy", {})
        if mypy:
            result["mypy_configured"] = True
            if mypy.get("strict"):
                result["mypy_strict"] = True
        ruff = tool.get("ruff", {})
        ruff_select = ruff.get("lint", {}).get("select") or ruff.get("select")
        if ruff_select:
            result["ruff_select"] = list(ruff_select)[:12]
        return result
    except Exception:
        return {}


def _extract_repo_signals(target_root: Path) -> dict[str, Any]:
    """Walk the full repository and extract aggregate AST-based governance signals.

    ADR-119 D3 B1: replaces file-sampling with a full-repo AST pass. Every .py
    file is parsed; aggregate counts and ratios replace raw file excerpts. The
    LLM receives measurements, not source text — more token-efficient and
    deterministic across runs on the same commit.
    """
    all_py = sorted(
        p for p in target_root.rglob("*.py") if _should_include_file(p, target_root)
    )

    files_parsed = 0
    files_failed = 0
    test_file_count = 0
    public_defs = 0
    public_defs_docstring = 0
    public_defs_annotated = 0
    public_classes = 0
    public_classes_docstring = 0
    future_annotations_files = 0
    type_checking_files = 0
    bare_except_count = 0
    typed_except_pass_count = 0
    print_call_count = 0
    abstract_methods = 0
    import_alias_counts: dict[str, int] = {}
    decorator_counts: dict[str, int] = {}

    for py_file in all_py:
        try:
            source = py_file.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(py_file))
        except Exception:
            files_failed += 1
            continue
        files_parsed += 1

        name = py_file.name
        if name.startswith("test_") or name.endswith("_test.py"):
            test_file_count += 1

        file_has_future = False
        file_has_type_checking = False

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module == "__future__" and any(
                    a.name == "annotations" for a in node.names
                ):
                    file_has_future = True

            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.asname:
                        key = f"import {alias.name} as {alias.asname}"
                        import_alias_counts[key] = import_alias_counts.get(key, 0) + 1

            elif isinstance(node, ast.If):
                test = node.test
                if (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
                    isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
                ):
                    file_has_type_checking = True

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith("_"):
                    public_defs += 1
                    if node.returns is not None:
                        public_defs_annotated += 1
                    if _has_docstring(node):
                        public_defs_docstring += 1
                    for dec in node.decorator_list:
                        dec_name = _get_decorator_name(dec)
                        if dec_name:
                            decorator_counts[dec_name] = (
                                decorator_counts.get(dec_name, 0) + 1
                            )
                        if dec_name == "abstractmethod":
                            abstract_methods += 1

            elif isinstance(node, ast.ClassDef):
                if not node.name.startswith("_"):
                    public_classes += 1
                    if _has_docstring(node):
                        public_classes_docstring += 1

            elif isinstance(node, ast.ExceptHandler):
                if node.type is None:
                    bare_except_count += 1
                elif len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                    typed_except_pass_count += 1

            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "print":
                    print_call_count += 1

        if file_has_future:
            future_annotations_files += 1
        if file_has_type_checking:
            type_checking_files += 1

    return {
        "total_py_files": len(all_py),
        "files_parsed": files_parsed,
        "files_failed": files_failed,
        "test_files": test_file_count,
        "has_src_layout": (target_root / "src").is_dir(),
        "public_defs": public_defs,
        "public_defs_docstring": public_defs_docstring,
        "public_defs_annotated": public_defs_annotated,
        "public_classes": public_classes,
        "public_classes_docstring": public_classes_docstring,
        "future_annotations_files": future_annotations_files,
        "type_checking_files": type_checking_files,
        "bare_except_count": bare_except_count,
        "typed_except_pass_count": typed_except_pass_count,
        "print_call_count": print_call_count,
        "abstract_methods": abstract_methods,
        "py_typed": (target_root / "py.typed").exists()
        or bool(list(target_root.glob("src/*/py.typed"))),
        "top_aliases": sorted(import_alias_counts.items(), key=lambda x: -x[1])[:8],
        "top_decorators": sorted(decorator_counts.items(), key=lambda x: -x[1])[:8],
        "ci_signals": _extract_ci_signals(target_root),
    }


def _format_signal_report(signals: dict[str, Any]) -> str:
    """Format aggregate repo signals as a structured text report for the LLM."""
    total = signals["total_py_files"]
    parsed = signals["files_parsed"]
    failed = signals["files_failed"]
    test_files = signals["test_files"]
    pub_defs = signals["public_defs"]
    annotated = signals["public_defs_annotated"]
    defs_doc = signals["public_defs_docstring"]
    pub_cls = signals["public_classes"]
    cls_doc = signals["public_classes_docstring"]
    future_ann = signals["future_annotations_files"]
    tc_files = signals["type_checking_files"]
    bare_exc = signals["bare_except_count"]
    typed_pass = signals["typed_except_pass_count"]
    prints = signals["print_call_count"]
    abstract = signals["abstract_methods"]
    py_typed = signals["py_typed"]

    # ID: 685a18bf-124b-4200-b005-5be86075cdf7
    def pct(n: int, of: int) -> str:
        return f"{int(n / of * 100)}%" if of else "n/a"

    parts: list[str] = [
        f"Python files: {total} total  {parsed} parsed  {failed} failed  {test_files} test files",
        f"Project layout: {'src/' if signals.get('has_src_layout') else 'flat'}  py.typed: {'yes' if py_typed else 'no'}",
        "",
        "Public symbols (full-repo, non-underscore functions and classes):",
        f"  functions/methods : {pub_defs}",
        f"    with return annotation : {annotated}  ({pct(annotated, pub_defs)})",
        f"    with docstring         : {defs_doc}  ({pct(defs_doc, pub_defs)})",
        f"  classes           : {pub_cls}",
        f"    with docstring         : {cls_doc}  ({pct(cls_doc, pub_cls)})",
        "",
        "Pattern counts (full-repo):",
        f"  from __future__ import annotations : {future_ann} files  ({pct(future_ann, parsed)})",
        f"  if TYPE_CHECKING guard             : {tc_files} files",
        f"  bare except (untyped)              : {bare_exc}",
        f"  typed except + pass (silenced)     : {typed_pass}",
        f"  print() calls                      : {prints}",
        f"  @abstractmethod usage              : {abstract}",
    ]

    top_aliases = signals.get("top_aliases", [])
    if top_aliases:
        parts += ["", "Import aliasing patterns (top by file count):"]
        for alias, count in top_aliases:
            parts.append(f"  {alias}  →  {count} files")

    top_dec = signals.get("top_decorators", [])
    if top_dec:
        parts += ["", "Decorator inventory (top by usage count):"]
        for dec, count in top_dec:
            parts.append(f"  @{dec}  →  {count} uses")

    ci = signals.get("ci_signals", {})
    if ci:
        parts += ["", "CI / tooling:"]
        if "mypy_configured" in ci:
            strict = ci.get("mypy_strict", False)
            parts.append(
                f"  mypy: configured  {'strict=true' if strict else 'non-strict'}"
            )
        ruff_select = ci.get("ruff_select")
        if ruff_select:
            parts.append(f"  ruff select: {ruff_select}")

    return "\n".join(parts)


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
    rules = []
    for c in confirmed:
        rule: dict[str, Any] = {
            "id": c["rule_id"],
            "statement": c["statement"],
            "authority": "policy",
            "phase": "runtime",
            "enforcement": c["enforcement"],
            "rationale": c.get("rationale", ""),
        }
        if not c.get("enforcement_matched"):
            rule["enforcement_note"] = (
                "declared-only: no enforcement catalog entry exists for this rule. "
                "To add enforcement, extend var/prompts/scout_rule_inducer/enforcement_catalog.yaml "
                "with an entry whose match_keys include a substring of this rule's id."
            )
        rules.append(rule)
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
