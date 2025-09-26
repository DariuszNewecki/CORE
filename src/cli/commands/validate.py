# src/system/admin/validate.py
"""
Provides CLI commands for validating constitutional and governance integrity.
This module consolidates and houses the logic from the old src/core/cli tools.
"""
from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import typer
from jsonschema import ValidationError, validate

from shared.config_loader import load_yaml_file
from shared.logger import getLogger

log = getLogger("core_admin.validate")

validate_app = typer.Typer(help="Commands for validating constitutional integrity.")


def _load_json(path: Path) -> dict:
    """Loads and returns a JSON dictionary from the specified file path."""
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _validate_schema_pair(pair: Tuple[Path, Path]) -> str | None:
    """Validates a YAML file against a JSON Schema, returning an error message or None."""
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


@validate_app.command("intent-schema")
# ID: 35d3d2a1-f012-4ce6-af61-86ace0f8f37d
def validate_intent_schema(
    intent_path: Path = typer.Option(
        Path(".intent"), "--intent-path", help="Path to the .intent directory."
    ),
):
    """Validate policy YAMLs under .intent/charter using their corresponding JSON Schemas."""
    log.info("Running intent schema validation via core-admin...")
    base = intent_path / "charter"

    # --- THIS IS THE FIX ---
    # The list now points to the correct, consolidated policies and schemas.
    checks: List[Tuple[Path, Path]] = [
        (
            base / "policies" / "agent_policy.yaml",
            base / "schemas" / "agent_policy_schema.json",
        ),
        (
            base / "policies" / "database_policy.yaml",
            base / "schemas" / "database_policy_schema.json",
        ),
        (
            base / "policies" / "canary_policy.yaml",
            base / "schemas" / "canary_policy_schema.json",
        ),
        (
            base / "policies" / "enforcement_model_policy.yaml",
            base / "schemas" / "enforcement_model_schema.json",
        ),
        (
            base / "policies" / "reporting_policy.yaml",
            base / "schemas" / "reporting_policy_schema.json",
        ),
    ]
    # --- END OF FIX ---

    errors = list(filter(None, (_validate_schema_pair(p) for p in checks)))
    if errors:
        typer.echo("\n".join(errors), err=True)
        raise typer.Exit(code=1)
    typer.echo("All checked .intent policy files are valid.")


@dataclass
# ID: cf80ad7c-42cd-4b45-8cf7-6f8d461707b6
class ReviewContext:
    risk_tier: str = "low"
    score: float = 0.0
    touches_critical_paths: bool = False
    checkpoint: bool = False
    canary: bool = False
    approver_quorum: bool = False


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


def _safe_eval(expr: str, ctx: Dict[str, Any]) -> bool:
    """Safely evaluate a boolean expression string against a context dictionary using AST validation."""
    expr = expr.replace(" true", " True").replace(" false", " False")
    tree = ast.parse(expr, mode="eval")
    for node in ast.walk(tree):
        if type(node) not in _ALLOWED_NODES:
            raise ValueError(f"Unsupported expression node: {type(node).__name__}")
        if isinstance(node, ast.Name) and node.id not in ctx:
            raise ValueError(f"Unknown identifier in condition: {node.id}")
    return bool(eval(compile(tree, "<cond>", "eval"), {"__builtins__": {}}, ctx))


def _merge_contexts(a: ReviewContext, b: ReviewContext) -> ReviewContext:
    return ReviewContext(
        risk_tier=b.risk_tier or a.risk_tier,
        score=b.score if b.score != 0.0 else a.score,
        touches_critical_paths=b.touches_critical_paths or a.touches_critical_paths,
        checkpoint=b.checkpoint or a.checkpoint,
        canary=b.canary or a.canary,
        approver_quorum=b.approver_quorum or a.approver_quorum,
    )


@validate_app.command("risk-gates")
# ID: 198e105d-51e8-4c3d-9129-e42c3898356e
def validate_risk_gates(
    mind_path: Path = typer.Option(
        Path(".intent/mind"), "--mind-path", help="Path to the .intent/mind directory."
    ),
    context: Optional[Path] = typer.Option(None, "--context"),
    risk_tier: str = typer.Option("low", "--risk-tier"),
    score: float = typer.Option(0.0, "--score"),
    touches_critical_paths: bool = typer.Option(
        False, "--touches-critical-paths/--no-touches-critical-paths"
    ),
    checkpoint: bool = typer.Option(False, "--checkpoint/--no-checkpoint"),
    canary: bool = typer.Option(False, "--canary/--no-canary"),
    approver_quorum: bool = typer.Option(
        False, "--approver-quorum/--no-approver-quorum"
    ),
):
    """Enforce risk-tier gates from score_policy.yaml."""
    log.info("Running risk gate validation via core-admin...")
    spath = mind_path / "evaluation" / "score_policy.yaml"
    if not spath.exists():
        typer.echo(f"Missing score policy: {spath}", err=True)
        raise typer.Exit(code=2)

    policy = load_yaml_file(spath)
    gates: Dict[str, Any] = policy.get("risk_tier_gates", {})
    conds: Dict[str, str] = policy.get("gate_conditions", {})

    file_ctx = ReviewContext()
    if context and context.exists():
        raw = load_yaml_file(context)
        file_ctx = ReviewContext(**raw)

    cli_ctx = ReviewContext(
        risk_tier, score, touches_critical_paths, checkpoint, canary, approver_quorum
    )
    ctx = _merge_contexts(file_ctx, cli_ctx)

    violations: List[str] = []
    tier = gates.get(ctx.risk_tier, {})
    min_score = float(tier.get("min_score", 0.0))
    required_flags = set(tier.get("require", []))

    if ctx.score < min_score:
        violations.append(
            f"score {ctx.score:.2f} < min_score {min_score:.2f} for tier '{ctx.risk_tier}'"
        )

    cond_env = ctx.__dict__
    for cond_key, flag_name in [
        ("checkpoint_required_when", "checkpoint"),
        ("canary_required_when", "canary"),
        ("approver_quorum_required_when", "approver_quorum"),
    ]:
        expr = conds.get(cond_key)
        if expr and _safe_eval(expr, cond_env):
            required_flags.add(flag_name)

    for flag in sorted(required_flags):
        if not bool(getattr(ctx, flag, False)):
            violations.append(
                f"required '{flag}' is missing/false for tier '{ctx.risk_tier}'"
            )

    if violations:
        typer.echo("Risk gate violations:", err=True)
        for v in violations:
            typer.echo(f" - {v}", err=True)
        raise typer.Exit(code=1)

    typer.echo("Risk gates satisfied ✓")


# ID: 140e067e-54a1-437f-b02b-8a9f0f64a7f2
def register(app: typer.Typer):
    """Register the 'validate' command group with the main CLI app."""
    app.add_typer(validate_app, name="validate")
