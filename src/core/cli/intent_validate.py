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
import sys
from pathlib import Path
from typing import List, Tuple

import typer
import yaml
from jsonschema import ValidationError, validate

app = typer.Typer(add_completion=False, help="Validate .intent policies against JSON Schemas.")

from typing import Any, Dict

from shared.utils.yaml_loader import load_yaml_file


def _load_yaml(file_path: str) -> Dict[str, Any]:
    """Load and parse YAML file from given path."""
    return load_yaml_file(file_path)

def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def _check(pair: Tuple[Path, Path]) -> str | None:
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
    mind_path: Path = typer.Option(Path(".intent"), "--mind-path", help="Path to the .intent directory."),
) -> None:
    """Validate policy YAMLs under .intent using JSON Schemas."""
    base = mind_path
    checks: List[Tuple[Path, Path]] = [
        (base / "policies" / "data_privacy.yaml",   base / "schemas" / "data_privacy_policy.schema.json"),
        (base / "policies" / "data_retention.yaml", base / "schemas" / "data_retention_policy.schema.json"),
        (base / "policies" / "canary_policy.yaml",  base / "schemas" / "canary_policy.schema.json"),
    ]
    errors = list(filter(None, (_check(p) for p in checks)))
    if errors:
        typer.echo("\n".join(errors), err=True)
        raise typer.Exit(code=1)
    typer.echo("All .intent policy files are valid.")

if __name__ == "__main__":
    app()