# src/core/cli/risk_gates.py
"""
Enforce risk-tier gates defined in .intent/evaluation/score_policy.yaml.

Usage examples (from repo root):
  # Provide context via CLI flags
  python -m src.core.cli.risk_gates check --risk-tier high --score 0.92 \
      --touches-critical-paths --checkpoint --canary --approver-quorum

  # Or use a simple review context file, then optionally override via CLI flags
  python -m src.core.cli.risk_gates check --context review_context.yaml
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import typer

from shared.utils.yaml_loader import load_yaml_file

app = typer.Typer(
    add_completion=False, help="Apply risk-tier gates from score_policy.yaml."
)


@dataclass
class ReviewContext:
    """A data structure holding the context for a governance review."""

    risk_tier: str = "low"
    score: float = 0.0
    touches_critical_paths: bool = False
    checkpoint: bool = False
    canary: bool = False
    approver_quorum: bool = False


# ---- Safe condition evaluator (supports: names, bool ops, comparisons, 'in') ----
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
    """Safely evaluates a simple boolean expression from a string, allowing only a small subset of Python's AST nodes."""
    # Normalize booleans (true/false) commonly used in YAML-like strings.
    expr = expr.replace(" true", " True").replace(" false", " False")
    tree = ast.parse(expr, mode="eval")
    for node in ast.walk(tree):
        if type(node) not in _ALLOWED_NODES:
            raise ValueError(f"Unsupported expression node: {type(node).__name__}")
        if isinstance(node, ast.Name) and node.id not in ctx:
            raise ValueError(f"Unknown identifier in condition: {node.id}")
    return bool(eval(compile(tree, "<cond>", "eval"), {"__builtins__": {}}, ctx))


def _load_yaml(file_path: str) -> Optional[Dict[str, Any]]:
    """Load YAML content from a file using the shared utility function."""
    return load_yaml_file(file_path)


def _merge(a: ReviewContext, b: ReviewContext) -> ReviewContext:
    """Merges two ReviewContext objects, preferring non-default values from `b` when available."""
    # CLI flags override file context when provided (typer passes defaults if not set).
    return ReviewContext(
        risk_tier=b.risk_tier or a.risk_tier,
        score=b.score if b.score != 0.0 else a.score,
        touches_critical_paths=b.touches_critical_paths or a.touches_critical_paths,
        checkpoint=b.checkpoint or a.checkpoint,
        canary=b.canary or a.canary,
        approver_quorum=b.approver_quorum or a.approver_quorum,
    )


@app.command("check")
def check(
    mind_path: Path = typer.Option(
        Path(".intent"), "--mind-path", help="Path to the .intent directory."
    ),
    context: Optional[Path] = typer.Option(
        None, "--context", help="YAML with review context fields."
    ),
    risk_tier: str = typer.Option(
        "low", "--risk-tier", case_sensitive=False, help="low|medium|high"
    ),
    score: float = typer.Option(0.0, "--score", help="Governance audit score (0..1)"),
    touches_critical_paths: bool = typer.Option(
        False, "--touches-critical-paths/--no-touches-critical-paths"
    ),
    checkpoint: bool = typer.Option(False, "--checkpoint/--no-checkpoint"),
    canary: bool = typer.Option(False, "--canary/--no-canary"),
    approver_quorum: bool = typer.Option(
        False, "--approver-quorum/--no-approver-quorum"
    ),
) -> None:
    """
    Enforce the gates defined in evaluation/score_policy.yaml using the given context.
    Fails (exit 1) if any requirement is not satisfied.
    """
    base = mind_path
    spath = base / "evaluation" / "score_policy.yaml"
    if not spath.exists():
        typer.echo(f"Missing score policy: {spath}", err=True)
        raise typer.Exit(code=2)

    policy = _load_yaml(spath)
    gates: Dict[str, Any] = policy.get("risk_tier_gates", {})
    conds: Dict[str, str] = policy.get("gate_conditions", {})

    file_ctx = ReviewContext()
    if context and context.exists():
        raw = _load_yaml(context)
        file_ctx = ReviewContext(
            risk_tier=str(raw.get("risk_tier", "low")).lower(),
            score=float(raw.get("score", 0.0)),
            touches_critical_paths=bool(raw.get("touches_critical_paths", False)),
            checkpoint=bool(raw.get("checkpoint", False)),
            canary=bool(raw.get("canary", False)),
            approver_quorum=bool(raw.get("approver_quorum", False)),
        )

    cli_ctx = ReviewContext(
        risk_tier=risk_tier.lower(),
        score=score,
        touches_critical_paths=touches_critical_paths,
        checkpoint=checkpoint,
        canary=canary,
        approver_quorum=approver_quorum,
    )
    ctx = _merge(file_ctx, cli_ctx)

    violations: List[str] = []

    # 1) Risk-tier specific min score + required flags
    tier = gates.get(ctx.risk_tier, {}) if isinstance(gates, dict) else {}
    min_score = float(tier.get("min_score", 0.0))
    required_flags = set(
        tier.get("require", []) if isinstance(tier.get("require", []), list) else []
    )

    if ctx.score < min_score:
        violations.append(
            f"score {ctx.score:.2f} < min_score {min_score:.2f} for tier '{ctx.risk_tier}'"
        )

    # 2) Gate conditions (declarative rules)
    cond_env = {
        "risk_tier": ctx.risk_tier,
        "touches_critical_paths": ctx.touches_critical_paths,
        "checkpoint": ctx.checkpoint,
        "canary": ctx.canary,
        "approver_quorum": ctx.approver_quorum,
        "score": ctx.score,
    }

    # This inner function is a helper and does not require its own docstring
    # as its purpose is clear from the context of this single command.
    def require_if(cond_key: str, flag_name: str) -> None:
        """Conditionally adds `flag_name` to the required set if the evaluated expression from `cond_key` is truthy."""
        expr = conds.get(cond_key)
        if not expr:
            return
        try:
            needed = _safe_eval(expr, cond_env)
        except Exception as e:
            violations.append(f"Invalid gate condition '{cond_key}': {e}")
            return
        if needed:
            required_flags.add(flag_name)

    require_if("checkpoint_required_when", "checkpoint")
    require_if("canary_required_when", "canary")
    require_if("approver_quorum_required_when", "approver_quorum")

    # 3) Check required flags are present/true in context
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


if __name__ == "__main__":
    app()
