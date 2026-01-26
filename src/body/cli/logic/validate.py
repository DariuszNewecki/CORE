# src/body/cli/logic/validate.py
# ID: cli.logic.validate
"""
CLI commands for validating constitutional and governance integrity.

CONSTITUTIONAL ALIGNMENT:
- Single Responsibility: CLI presentation and user interaction
- Delegates validation logic to services
- Thin adapter layer

Extracted responsibilities:
- Schema validation → IntentSchemaValidator
- Expression evaluation → PolicyExpressionEvaluator
"""

from __future__ import annotations

from pathlib import Path

import typer

from body.services.intent_schema_validator import IntentSchemaValidator
from body.services.policy_expression_evaluator import (
    PolicyExpressionEvaluator,
    ReviewContext,
)
from shared.logger import getLogger


logger = getLogger(__name__)
validate_app = typer.Typer(help="Commands for validating constitutional integrity.")


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
        * If it has a `$schema` field → validate against that JSON Schema.
        * If it has no `$schema` field → report as [SKIP], but do NOT fail.

    This allows gradual rollout of schema governance across the Mind.
    """
    logger.info("Running .intent JSON-schema validation via core-admin.")

    # Use service for validation logic
    validator = IntentSchemaValidator(intent_path.resolve())
    results, skipped = validator.validate_all()

    # CLI presentation logic
    if not results:
        typer.echo("No .intent YAML files with $schema found. Nothing to validate.")
        if skipped:
            _print_skipped(skipped)
        return

    # Print results
    errors = []
    for result in results:
        if result.is_valid:
            typer.echo(f"[OK] {result.yaml_path} ✓")
        else:
            errors.append(f"[FAIL] {result.yaml_path}: {result.error_message}")

    # Handle failures
    if errors:
        typer.echo("\nSchema validation errors:", err=True)
        typer.echo("\n".join(errors), err=True)
        raise typer.Exit(code=1)

    typer.echo("\nAll .intent documents with $schema validated successfully.")

    if skipped:
        _print_skipped(skipped)


def _print_skipped(skipped: list[str]) -> None:
    """Print skipped files message."""
    typer.echo("\nSkipped files (no $schema yet):")
    for msg in skipped:
        typer.echo(f"  {msg}")


# ---------------------------------------------------------------------------
# Re-export for backward compatibility
# ---------------------------------------------------------------------------

# Export ReviewContext and evaluator for any code that imports from here
__all__ = [
    "PolicyExpressionEvaluator",
    "ReviewContext",
    "validate_app",
]
