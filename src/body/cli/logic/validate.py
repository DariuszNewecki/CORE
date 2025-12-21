# src/body/cli/logic/validate.py
# ID: cli.logic.validate
"""
Provides CLI commands for validating constitutional and governance integrity.
This module consolidates and houses the logic from the old src/core/cli tools.

Key responsibilities:

- Generic JSON Schema validation for .intent/ documents that declare `$schema`
  (starting with runtime requirements, but extensible to all Mind documents).
- Safe evaluation of simple boolean policy expressions as part of governance checks.
"""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import typer
from jsonschema import ValidationError, validate

from shared.config_loader import load_yaml_file
from shared.logger import getLogger


logger = getLogger(__name__)
validate_app = typer.Typer(help="Commands for validating constitutional integrity.")


# ---------------------------------------------------------------------------
# Low-level helpers for JSON Schema validation
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> dict:
    """Loads and returns a JSON dictionary from the specified file path."""
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _validate_schema_pair(pair: tuple[Path, Path]) -> str | None:
    """
    Validates a YAML file against a JSON Schema, returning an error message or None.

    pair[0] -> YAML document path
    pair[1] -> JSON Schema path
    """
    yml_path, schema_path = pair

    if not yml_path.exists():
        return f"Missing file: {yml_path}"

    if not schema_path.exists():
        return f"Missing schema: {schema_path}"

    try:
        data = load_yaml_file(yml_path)
        schema = _load_json(schema_path)
        validate(instance=data, schema=schema)
        typer.echo(f"[OK] {yml_path} ✓")
        return None
    except ValidationError as e:
        path = ".".join(map(str, e.path)) or "(root)"
        return f"[FAIL] {yml_path}: {e.message} at {path}"
    except Exception as e:
        return f"[ERROR] {yml_path}: Unexpected validation error: {e!r}"


def _iter_intent_yaml(intent_root: Path) -> list[Path]:
    """
    Return all YAML/YML files under the .intent root, excluding known state folders.

    NOTE:
        .intent is treated as the Mind, but some subtrees (runtime, exports, keys)
        are operational/stateful and are not governed by the same schema rules.
        Constitutional proposals are stored under work/proposals (not under .intent).
    """
    if not intent_root.exists():
        logger.error("Intent root %s does not exist", intent_root)
        return []

    exclude_prefixes = (
        "runtime/",
        "mind_export/",
        "keys/",
    )

    files: list[Path] = []

    # Collect .yaml and .yml without duplication
    seen: set[Path] = set()
    for pattern in ("**/*.yaml", "**/*.yml"):
        for path in intent_root.glob(pattern):
            if path in seen:
                continue
            rel = path.relative_to(intent_root).as_posix()
            if any(rel.startswith(prefix) for prefix in exclude_prefixes):
                continue
            seen.add(path)
            files.append(path)

    return sorted(files)


def _discover_schema_pairs(
    intent_root: Path,
) -> tuple[list[tuple[Path, Path]], list[str]]:
    """
    Discover YAML → JSON-schema pairs using the `$schema` field.

    Rules:
    - Only files with a top-level mapping and a `$schema` key are validated.
    - The `$schema` value is interpreted as a path relative to `.intent/`.
    - Files without `$schema` are currently SKIPPED (reported as informational),
      so you can incrementally roll schemas out across the Mind.

    Returns:
        (pairs, skipped_messages)
    """
    pairs: list[tuple[Path, Path]] = []
    skipped: list[str] = []

    for yaml_path in _iter_intent_yaml(intent_root):
        rel = yaml_path.relative_to(intent_root).as_posix()

        try:
            data = load_yaml_file(yaml_path)
        except Exception as exc:
            skipped.append(f"[SKIP] {rel}: YAML parse error: {exc!r}")
            continue

        if not isinstance(data, dict):
            skipped.append(f"[SKIP] {rel}: top-level YAML is not a mapping")
            continue

        schema_ref = data.get("$schema")
        if not schema_ref:
            # No explicit schema yet - this is allowed during migration.
            skipped.append(f"[SKIP] {rel}: no $schema field; not validated")
            continue

        schema_path = (intent_root / schema_ref).resolve()
        pairs.append((yaml_path, schema_path))

    return pairs, skipped


# ---------------------------------------------------------------------------
# CLI command: validate .intent against JSON Schemas
# ---------------------------------------------------------------------------


@validate_app.command("intent-schema")
# ID: fd640765-e202-4790-a133-95d1a2d8983
# ID: 3c97e5c8-ad67-4865-b636-0860ab74775b
def validate_intent_schema(
    intent_path: Path = typer.Option(
        Path(".intent"),
        "--intent-path",
        help="Path to the .intent directory (Mind root).",
    ),
) -> None:
    """
    Validate .intent YAML documents that declare `$schema` against their JSON Schemas.

    Current behaviour (A2 migration-friendly):
    - Walks `.intent/**` (excluding runtime/state folders).
    - For each YAML/YML file:
        * If it has a `$schema` field → treat it as a governed document and
          validate against that JSON Schema.
        * If it has no `$schema` field → report as [SKIP], but do NOT fail.

    This allows you to:
    - Start with a small set of schema-governed documents
      (e.g. mind/config/runtime_requirements.yaml).
    - Gradually roll out `$schema` headers to the rest of the Mind.
    """
    logger.info("Running .intent JSON-schema validation via core-admin.")
    intent_root = intent_path.resolve()

    pairs, skipped = _discover_schema_pairs(intent_root)

    if not pairs:
        typer.echo("No .intent YAML files with $schema found. Nothing to validate.")
        if skipped:
            typer.echo("\nSkipped files:")
            for msg in skipped:
                typer.echo(f"  {msg}")
        return

    errors = list(filter(None, (_validate_schema_pair(p) for p in pairs)))

    if errors:
        typer.echo("\nSchema validation errors:", err=True)
        typer.echo("\n".join(errors), err=True)
        raise typer.Exit(code=1)

    typer.echo("All .intent documents with $schema validated successfully.")

    if skipped:
        typer.echo("\nSkipped files (no $schema yet):")
        for msg in skipped:
            typer.echo(f"  {msg}")


# ---------------------------------------------------------------------------
# SAFE EVAL FOR GOVERNANCE EXPRESSIONS (unchanged)
# ---------------------------------------------------------------------------


@dataclass
# ID: 38a08d04-04d2-4196-bb0b-b95d2a227ae3
class ReviewContext:
    risk_tier: str = "low"
    score: float = 0.0
    touches_critical_paths: bool = False
    checkpoint: bool = False
    canary: bool = False
    approver_quorum: bool = False


# AST allowlist for safe policy evaluation
_ALLOWED_NODES = {
    ast.Expression,
    ast.BoolOp,
    ast.BinOp,
    ast.UnaryOp,
    ast.Compare,
    ast.Name,
    ast.Load,
    ast.Constant,
    ast.List,
    ast.Tuple,
    ast.And,
    ast.Or,
    ast.Not,
    ast.In,
    ast.Eq,
    ast.NotEq,
}


def _safe_eval(expr: str, ctx: dict[str, Any]) -> bool:
    """
    Safely evaluate a boolean expression string against a context dictionary using AST validation.

    SECURITY NOTE: This function uses eval() but is SAFE because:
    1. Input is parsed and validated via AST whitelist (_ALLOWED_NODES)
    2. Only safe nodes are permitted (no calls, imports, attribute access)
    3. Builtins are disabled ({"__builtins__": {}})
    4. Only whitelisted context variables are available
    5. Used exclusively for evaluating policy conditions from .intent/

    This is verified safe code execution for constitutional governance and has been
    reviewed for safety. The eval is bounded and cannot execute arbitrary code.
    """
    expr = expr.replace(" true", " True").replace(" false", " False")

    # Layer 2: AST Validation
    tree = ast.parse(expr, mode="eval")

    for node in ast.walk(tree):
        if type(node) not in _ALLOWED_NODES:
            raise ValueError(f"Disallowed node in expression: {type(node).__name__}")

    # Layer 3: Restricted Execution (Sandboxing)
    # SECURITY: Using compile() on validated AST is safer than eval(str)
    # SECURITY: __builtins__ is empty to prevent access to globals
    compiled = compile(tree, "<policy_expr>", "eval")

    # SECURITY: context variables only
    return bool(eval(compiled, {"__builtins__": {}}, ctx))
