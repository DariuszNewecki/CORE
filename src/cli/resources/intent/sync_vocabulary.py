# src/cli/resources/intent/sync_vocabulary.py
"""
core-admin intent sync vocabulary — regen .intent/META/vocabulary.json
from the canonical section of .specs/papers/CORE-Vocabulary.md (per ADR-023).
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

import typer
from rich.console import Console

from cli.utils import core_command
from shared.context import CoreContext
from shared.infrastructure.intent.vocabulary_projection import (
    CANONICAL_HEADING,
    VOCABULARY_JSON_REL,
    VOCABULARY_PAPER_REL,
    VocabularyProjectionError,
    load_vocabulary_projection,
    locate_canonical_section,
)
from shared.logger import getLogger
from shared.models.command_meta import CommandBehavior, CommandLayer, command_meta

from .hub import app


logger = getLogger(__name__)
console = Console()

REQUIRED_COLUMNS = ("term", "definition", "not", "authoritative_paper")
OPTIONAL_COLUMNS = ("aliases", "see_also")
GENERATOR_VERSION_FALLBACK = "core-admin@unknown"

_UNESCAPED_PIPE = re.compile(r"(?<!\\)\|")


# ID: 5d6c2e0b-ad12-4f8c-9b40-7c2c3e3c8a01
def _read_package_version() -> str:
    """Read the CLI package version from pyproject.toml; fall back if unavailable."""
    pyproject = Path(__file__).resolve().parents[4] / "pyproject.toml"
    if not pyproject.is_file():
        return GENERATOR_VERSION_FALLBACK
    try:
        for line in pyproject.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("version") and "=" in stripped:
                value = stripped.split("=", 1)[1].strip().strip('"').strip("'")
                if value:
                    return f"core-admin@{value}"
    except OSError:
        pass
    return GENERATOR_VERSION_FALLBACK


# ID: 7b3f1d8c-9a2e-4f1c-b3d7-2e8c6a4d9e03
def _split_row(row: str) -> list[str]:
    """Split a markdown table row on unescaped pipes; trim, unescape \\|."""
    body = row.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|"):
        body = body[:-1]
    cells = _UNESCAPED_PIPE.split(body)
    return [c.strip().replace("\\|", "|") for c in cells]


# ID: 2f5a4d8a-1c6b-4e9f-8a4d-3b9e1c7f4a04
def _split_list_cell(cell: str) -> list[str]:
    """Split a pipe-separated list cell on `\\|`; trim; drop empties."""
    if not cell.strip():
        return []
    parts = [p.strip() for p in cell.split("\\|")]
    return [p for p in parts if p]


# ID: 8c2d1f5e-7b9a-4f3c-9e2d-4a7c8e5b1f05
def _strip_inline_code(value: str) -> str:
    """Strip surrounding backticks from a markdown inline-code value."""
    v = value.strip()
    if v.startswith("`") and v.endswith("`") and len(v) >= 2:
        return v[1:-1].strip()
    return v


# ID: 6e1a4c7d-2b9f-4d8c-a3e1-5d8b2c9e1a06
def _parse_table(section_lines: list[str]) -> tuple[list[str], list[list[str]]]:
    """
    Extract the first markdown table from a section.

    Returns (header_cells, data_rows). Skips the markdown alignment-separator
    row immediately after the header. Stops at the first non-table line.
    """
    table_lines: list[str] = []
    in_table = False
    for line in section_lines:
        if line.lstrip().startswith("|"):
            in_table = True
            table_lines.append(line)
        elif in_table:
            break
    if len(table_lines) < 2:
        return [], []
    header = _split_row(table_lines[0])
    data_rows = [_split_row(r) for r in table_lines[2:]]
    return header, data_rows


# ID: 4a9c2e6d-3f7b-4d1c-8e9a-6c4f1b3d8a07
def _validate_columns(header: list[str]) -> list[str]:
    """Confirm the header begins with the required columns in order; report violations."""
    violations: list[str] = []
    for i, name in enumerate(REQUIRED_COLUMNS):
        if i >= len(header) or header[i] != name:
            actual = header[i] if i < len(header) else "<missing>"
            violations.append(f"column {i + 1}: expected '{name}', got '{actual}'")
    return violations


# ID: 1b8d3c5e-7a2f-4e9c-b1d8-9e4f2a3c8b08
def _parse_terms(
    header: list[str],
    rows: list[list[str]],
) -> tuple[list[dict], list[str]]:
    """
    Parse data rows into term dicts. Returns (terms, grammar_violations).

    A row is a violation if any required cell is empty or missing. Optional
    aliases/see_also columns are split on `\\|`; absent or empty cells produce
    empty arrays.
    """
    col_idx = {name: i for i, name in enumerate(header)}
    terms: list[dict] = []
    violations: list[str] = []
    for row_num, cells in enumerate(rows, start=1):
        if not any(c.strip() for c in cells):
            continue
        missing = [
            c
            for c in REQUIRED_COLUMNS
            if col_idx[c] >= len(cells) or not cells[col_idx[c]].strip()
        ]
        if missing:
            term_label = (
                cells[col_idx["term"]].strip()
                if col_idx["term"] < len(cells) and cells[col_idx["term"]].strip()
                else f"row {row_num}"
            )
            violations.append(
                f"row {row_num} ({term_label}): empty required cell(s): {', '.join(missing)}"
            )
            continue
        entry = {
            "term": cells[col_idx["term"]].strip(),
            "definition": cells[col_idx["definition"]].strip(),
            "not": cells[col_idx["not"]].strip(),
            "authoritative_paper": _strip_inline_code(
                cells[col_idx["authoritative_paper"]]
            ),
            "aliases": (
                _split_list_cell(cells[col_idx["aliases"]])
                if "aliases" in col_idx and col_idx["aliases"] < len(cells)
                else []
            ),
            "see_also": (
                _split_list_cell(cells[col_idx["see_also"]])
                if "see_also" in col_idx and col_idx["see_also"] < len(cells)
                else []
            ),
        }
        terms.append(entry)
    return terms, violations


# ID: 9c4e7b2a-5d1f-4a8c-b6e3-2f8a4c1e9d09
def _validate_paper_paths(terms: list[dict], repo_root: Path) -> list[str]:
    """Confirm every authoritative_paper resolves to an existing file under repo_root."""
    violations: list[str] = []
    for entry in terms:
        rel = entry["authoritative_paper"]
        target = (repo_root / rel).resolve()
        try:
            target.relative_to(repo_root.resolve())
        except ValueError:
            violations.append(f"{entry['term']}: path '{rel}' escapes repo root")
            continue
        if not target.is_file():
            violations.append(
                f"{entry['term']}: authoritative_paper '{rel}' does not exist"
            )
    return violations


# ID: 7d2a9f4c-8b3e-4f1d-a9c2-7e1b3f8c4d0a
def _load_existing_metadata(json_path: Path) -> tuple[str, dict[str, str]]:
    """
    Read existing $schema and metadata fields (id, title, version, authority, status)
    from vocabulary.json if present. Falls back to declared defaults when absent.
    """
    defaults_schema = "META/vocabulary.schema.json"
    defaults_meta = {
        "id": "core.vocabulary",
        "title": "CORE Canonical Vocabulary",
        "version": "1.0.0",
        "authority": "meta",
        "status": "active",
    }
    if not json_path.is_file():
        return defaults_schema, defaults_meta
    try:
        existing = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return defaults_schema, defaults_meta
    schema_value = existing.get("$schema", defaults_schema)
    existing_meta = existing.get("metadata", {})
    preserved = {
        key: existing_meta.get(key, defaults_meta[key]) for key in defaults_meta
    }
    return schema_value, preserved


# ID: 2c8e1b4f-9a7d-4c3e-b8f1-5d2a9c4e7b0b
def _build_projection(
    schema_value: str,
    preserved_meta: dict[str, str],
    source_hash: str,
    generated_at: str,
    generator_version: str,
    terms: list[dict],
) -> dict:
    """Assemble the JSON projection structure with stable key order."""
    metadata = {
        "id": preserved_meta["id"],
        "title": preserved_meta["title"],
        "version": preserved_meta["version"],
        "authority": preserved_meta["authority"],
        "status": preserved_meta["status"],
        "source_hash": source_hash,
        "generated_at": generated_at,
        "generator_version": generator_version,
    }
    sorted_terms = sorted(terms, key=lambda t: t["term"].casefold())
    return {
        "$schema": schema_value,
        "kind": "vocabulary",
        "metadata": metadata,
        "terms": sorted_terms,
    }


@app.command("sync")
@command_meta(
    canonical_name="intent.sync",
    behavior=CommandBehavior.MUTATE,
    layer=CommandLayer.MIND,
    summary="Regenerate a .intent/ projection from its source paper (ADR-023).",
    dangerous=True,
)
@core_command(requires_context=True, dangerous=True)
# ID: a1f4e8c2-3b7d-4f9e-a2c1-8d6b5e3a4f0c
async def sync_intent(
    ctx: typer.Context,
    target: str = typer.Argument(
        ..., help="Projection target. Currently supported: 'vocabulary'."
    ),
    write: bool = typer.Option(
        False, "--write", help="Apply changes to the projection file."
    ),
    check: bool = typer.Option(
        False,
        "--check",
        help=(
            "Verify the projection is fresh (CI gate per ADR-023 D6). "
            "Exits 0 if healthy, 1 if drift or broken. Mutually exclusive with --write."
        ),
    ),
) -> None:
    """
    Regenerate a .intent/ projection from its canonical source paper.

    Target 'vocabulary' parses the canonical section of
    .specs/papers/CORE-Vocabulary.md and emits .intent/META/vocabulary.json.
    """
    if target != "vocabulary":
        console.print(f"[bold red]Unsupported target:[/bold red] {target}")
        console.print("Supported targets: vocabulary")
        raise typer.Exit(2)

    if check and write:
        console.print(
            "[bold red]--check and --write are mutually exclusive.[/bold red]"
        )
        raise typer.Exit(2)

    core_context: CoreContext = ctx.obj
    repo_root: Path = core_context.git_service.repo_path

    if check:
        projection = load_vocabulary_projection(repo_root)
        if isinstance(projection, VocabularyProjectionError):
            console.print(projection.reason)
            raise typer.Exit(1)
        if projection.state == "drift":
            console.print(
                "vocabulary.json is stale — source_hash does not match the "
                "current canonical section.\n"
                "Run: core-admin intent sync vocabulary --write\n"
                "Then commit the updated vocabulary.json before merging."
            )
            raise typer.Exit(1)
        console.print(
            "vocabulary.json is up to date (source_hash matches canonical section)"
        )
        return

    paper_path = repo_root / VOCABULARY_PAPER_REL
    json_path = repo_root / VOCABULARY_JSON_REL

    if not paper_path.is_file():
        console.print(f"[bold red]Source paper not found:[/bold red] {paper_path}")
        raise typer.Exit(1)

    paper_text = paper_path.read_text(encoding="utf-8")
    section_range = locate_canonical_section(paper_text)
    if section_range is None:
        console.print(
            f"[bold red]Canonical section not found.[/bold red] "
            f"Expected heading: '{CANONICAL_HEADING}' in {VOCABULARY_PAPER_REL}"
        )
        raise typer.Exit(1)

    start, end = section_range
    section_lines = paper_text.splitlines()[start:end]
    section_text = "\n".join(section_lines)
    source_hash = hashlib.sha256(section_text.encode("utf-8")).hexdigest()

    header, rows = _parse_table(section_lines)
    if not header:
        console.print(
            "[bold red]No markdown table found in canonical section.[/bold red]"
        )
        raise typer.Exit(1)

    column_violations = _validate_columns(header)
    if column_violations:
        console.print(
            "[bold red]Canonical-section column grammar violations:[/bold red]"
        )
        for v in column_violations:
            console.print(f"  - {v}")
        raise typer.Exit(1)

    terms, grammar_violations = _parse_terms(header, rows)
    path_violations = _validate_paper_paths(terms, repo_root)

    if grammar_violations or path_violations:
        if grammar_violations:
            console.print("[bold red]Grammar violations:[/bold red]")
            for v in grammar_violations:
                console.print(f"  - {v}")
        if path_violations:
            console.print("[bold red]Authoritative-paper path violations:[/bold red]")
            for v in path_violations:
                console.print(f"  - {v}")
        raise typer.Exit(1)

    schema_value, preserved_meta = _load_existing_metadata(json_path)
    generated_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    generator_version = _read_package_version()

    projection = _build_projection(
        schema_value=schema_value,
        preserved_meta=preserved_meta,
        source_hash=source_hash,
        generated_at=generated_at,
        generator_version=generator_version,
        terms=terms,
    )

    rendered = json.dumps(projection, indent=2, ensure_ascii=False) + "\n"

    mode = "WRITE" if write else "DRY-RUN"
    console.print(f"[bold cyan]Vocabulary sync ({mode})[/bold cyan]")
    console.print(f"  source:        {VOCABULARY_PAPER_REL}")
    console.print(f"  target:        {VOCABULARY_JSON_REL}")
    console.print(f"  terms:         {len(terms)}")
    console.print(f"  source_hash:   {source_hash[:16]}…")
    console.print(f"  generated_at:  {generated_at}")
    console.print(f"  generator:     {generator_version}")

    if write:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(rendered, encoding="utf-8")
        console.print(f"[bold green]✓ Wrote {VOCABULARY_JSON_REL}[/bold green]")
    else:
        console.print(
            "[yellow]Dry-run: no file written. Pass --write to apply.[/yellow]"
        )
