# src/core/cli/intent_validate.py
"""
Local validator for .intent policy YAMLs against JSON Schemas.
Usage (from repo root):
  python -m src.core.cli.intent_validate
  # or (after wiring into your CLI)
  core-admin validate-intent
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import typer
from jsonschema import ValidationError, validate

from shared.utils.yaml_loader import load_yaml_file

app = typer.Typer(
    add_completion=False, help="Validate .intent policies against JSON Schemas."
)


def _load_yaml(file_path: str) -> Dict[str, Any]:
    """Load YAML content from a file.

    Args:
        file_path: Path to the YAML file

    Returns:
        Parsed YAML content as dictionary

    Raises:
        FileNotFoundError: If the file doesn't exist
        yaml.YAMLError: If the YAML is invalid
    """
    return load_yaml_file(file_path)


def _load_json(path: Path) -> dict:
    """Loads and returns a JSON dictionary from the specified file path."""
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _check(pair: Tuple[Path, Path]) -> str | None:
    """Validates a YAML file against a JSON Schema, returning an error message if validation fails or files are missing, or None if successful."""
    yml_path, schema_path = pair
    if not yml_path.exists():
        return f"Missing file: {yml_path}"
    if not schema_path.exists():
        return f"Missing schema: {schema_path}"
    try:
        data = _load_yaml(yml_path)
        schema = _load_json(schema_path)
        validate(instance=data, schema=schema)
        typer.echo(f"[OK] {yml_path} ✓")
        return None
    except ValidationError as e:
        path = ".".join(map(str, e.path)) or "(root)"
        return f"[FAIL] {yml_path}: {e.message} at {path}"


@app.command("run")
def run(
    mind_path: Path = typer.Option(
        Path(".intent"), "--mind-path", help="Path to the .intent directory."
    ),
) -> None:
    """Validate policy YAMLs under .intent using JSON Schemas."""
    base = mind_path
    checks: List[Tuple[Path, Path]] = [
        (
            base / "policies" / "data_privacy.yaml",
            base / "schemas" / "data_privacy_policy.schema.json",
        ),
        (
            base / "policies" / "data_retention.yaml",
            base / "schemas" / "data_retention_policy.schema.json",
        ),
        (
            base / "policies" / "canary_policy.yaml",
            base / "schemas" / "canary_policy.schema.json",
        ),
    ]
    errors = list(filter(None, (_check(p) for p in checks)))
    if errors:
        typer.echo("\n".join(errors), err=True)
        raise typer.Exit(code=1)
    typer.echo("All .intent policy files are valid.")


if __name__ == "__main__":
    app()
