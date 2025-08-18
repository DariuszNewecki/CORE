# src/system/admin.py
"""
CORE Admin CLI (Poetry script: core-admin)

Commands
--------
- core-admin guard check [--format pretty|json] [--no-fail]
    Runs the Intent Guard (AST-based import checks) using .intent policies.
    Uses the same logic as src/system/tools/intent_guard_runner.py (File 12).

- core-admin guard drift [--format short|pretty|json]
    Displays the drift evidence written by manifest_migrator (File 4),
    reading the evidence path from .intent/meta.yaml (reports.drift).

- core-admin fix docstrings [--write]
    Placeholder (safe no-op). Kept so Makefile target doesn't break.

Notes
-----
- This CLI is intentionally light and constitution-aware. Paths are resolved
  from .intent/meta.yaml whenever possible.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import typer
import yaml

app = typer.Typer(help="CORE Admin CLI")
guard_app = typer.Typer(help="Constitutional guard utilities")
fix_app = typer.Typer(help="Developer productivity helpers")

app.add_typer(guard_app, name="guard")
app.add_typer(fix_app, name="fix")


# ---------- Utilities ---------------------------------------------------------

REPO = (
    Path(__file__).resolve().parents[2]
)  # .../src/system/admin.py -> repo root candidate
INTENT = (REPO / ".intent") if (REPO / ".intent").exists() else Path(".intent")


def _load_yaml(p: Path) -> dict:
    if not p.exists():
        typer.secho(f"ERROR: Missing file: {p}", fg=typer.colors.RED, err=True)
        raise typer.Exit(2)
    try:
        return yaml.safe_load(p.read_text()) or {}
    except Exception as e:
        typer.secho(f"ERROR: YAML error in {p}: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(2)


def _meta_paths() -> tuple[Path, Path]:
    meta = _load_yaml(INTENT / "meta.yaml")
    pol = meta.get("policies", {})
    knowledge = meta.get("knowledge", {})
    reports = meta.get("reports", {})

    policy_path = INTENT / pol.get("intent_guard", "policies/intent_guard.yaml")
    source_map = INTENT / knowledge.get(
        "source_structure", "knowledge/source_structure.yaml"
    )
    drift_path = (Path(reports.get("drift", "reports/drift_report.json"))).resolve()
    return policy_path, source_map, drift_path


# ---------- guard check -------------------------------------------------------


@guard_app.command("check")
def guard_check(
    fmt: str = typer.Option("pretty", "--format", help="Output format: pretty|json"),
    no_fail: bool = typer.Option(
        False, "--no-fail", help="Always exit 0 (override enforcement.mode)"
    ),
):
    """
    Run Intent Guard (import/dependency checks).
    """
    # Import the runner and call its main() with args.
    try:
        from system.tools.intent_guard_runner import (
            main as guard_runner_main,  # type: ignore
        )
    except Exception as e:  # pragma: no cover
        typer.secho(
            f"ERROR: guard runner unavailable: {e}", fg=typer.colors.RED, err=True
        )
        raise typer.Exit(2)

    argv = ["check", f"--format={fmt}"] + (["--no-fail"] if no_fail else [])
    try:
        guard_runner_main(argv)  # will sys.exit() internally
    except SystemExit as exc:
        # Propagate exit code so Makefile can fail if needed.
        raise typer.Exit(exc.code)


# ---------- guard drift -------------------------------------------------------


@dataclass
class DriftSummary:
    validation_errors: int
    duplicate_caps: int


def _summarize_drift(payload: dict) -> DriftSummary:
    val_errs = payload.get("validation_errors") or []
    dups = payload.get("duplicates") or {}
    return DriftSummary(validation_errors=len(val_errs), duplicate_caps=len(dups))


@guard_app.command("drift")
def guard_drift(
    fmt: str = typer.Option(
        "short", "--format", help="Output format: short|pretty|json"
    ),
):
    """
    Display drift evidence produced by manifest_migrator (schema errors + capability duplicates).
    """
    _, _, drift_path = _meta_paths()

    if not drift_path.exists():
        typer.secho(
            f"⚠️  No drift evidence found at {drift_path}. "
            f"Hint: run `make drift` or `make migrate` first.",
            fg=typer.colors.YELLOW,
        )
        raise typer.Exit(0)

    try:
        payload = json.loads(drift_path.read_text())
    except Exception as e:
        typer.secho(
            f"ERROR: Invalid JSON in {drift_path}: {e}", fg=typer.colors.RED, err=True
        )
        raise typer.Exit(2)

    if fmt == "json":
        typer.echo(json.dumps(payload, indent=2))
        raise typer.Exit(0)

    summary = _summarize_drift(payload)

    if fmt == "short":
        msg = f"validation_errors={summary.validation_errors} duplicate_capabilities={summary.duplicate_caps}"
        color = (
            typer.colors.GREEN
            if (summary.validation_errors == 0 and summary.duplicate_caps == 0)
            else typer.colors.RED
        )
        typer.secho(msg, fg=color)
        raise typer.Exit(0)

    # pretty
    try:
        from rich import box
        from rich.console import Console
        from rich.table import Table

        console = Console()
        table = Table(title="Capability Drift", box=box.SIMPLE_HEAVY)
        table.add_column("Metric")
        table.add_column("Count")
        table.add_row("Schema validation errors", str(summary.validation_errors))
        table.add_row("Duplicate capabilities", str(summary.duplicate_caps))
        console.print(table)

        # Show details if any
        if payload.get("validation_errors"):
            console.print("\n[bold]Validation Errors[/]")
            for line in payload["validation_errors"]:
                console.print(f" - {line}")

        if payload.get("duplicates"):
            console.print("\n[bold]Duplicates[/]")
            for cap, doms in sorted(payload["duplicates"].items()):
                console.print(f" - {cap}: {', '.join(sorted(doms))}")

    except Exception:
        # Fallback to plain text
        typer.echo("Capability Drift")
        typer.echo(f"- Schema validation errors: {summary.validation_errors}")
        typer.echo(f"- Duplicate capabilities: {summary.duplicate_caps}")

    raise typer.Exit(0)


# ---------- fix docstrings (placeholder) -------------------------------------


@fix_app.command("docstrings")
def fix_docstrings(
    write: bool = typer.Option(
        False, "--write", help="(Placeholder) If set, would apply fixes in place."
    ),
):
    """
    Placeholder command so 'make fix-docstrings' doesn't break.
    """
    typer.secho(
        "ℹ️  Docstring fixer not wired yet. This is a safe placeholder.",
        fg=typer.colors.YELLOW,
    )
    if write:
        typer.secho(
            "Pretending to write fixes... (no changes made)", fg=typer.colors.BLUE
        )
    raise typer.Exit(0)


# ---------- Main --------------------------------------------------------------

if __name__ == "__main__":
    app()
