# src/shared/schemas/manifest_validator.py
"""
Provides utilities for validating manifest entries against JSON schemas using jsonschema.
"""

from __future__ import annotations

import json
from typing import Any, cast

import jsonschema

from shared.path_utils import get_repo_root


# --- THIS IS THE FIX ---
# The single source of truth for the location of constitutional schemas.
SCHEMA_DIR = get_repo_root() / ".intent" / "charter" / "schemas"
# --- END OF FIX ---


# ID: cfab52b8-8fed-4536-bc75-ed81a1161331
def load_schema(schema_name: str) -> dict[str, Any]:
    """
    Load a JSON schema from the .intent/schemas/ directory.
    """
    schema_path = SCHEMA_DIR / schema_name

    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")

    try:
        with open(schema_path, encoding="utf-8") as f:
            # FIXED: Added cast for MyPy
            return cast(dict[str, Any], json.load(f))
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(
            f"Invalid JSON in schema file {schema_path}: {e.msg}", e.doc, e.pos
        )


# ID: 047e2cb8-1e18-4175-9be2-1017a2fba3d7
def validate_manifest_entry(
    entry: dict[str, Any], schema_name: str = "knowledge_graph_entry.schema.json"
) -> tuple[bool, list[str]]:
    """
    Validate a single manifest entry against a schema.
    """
    try:
        schema = load_schema(schema_name)
    except Exception as e:
        return False, [f"Failed to load schema '{schema_name}': {e}"]

    # Use Draft7Validator for compatibility with our schema definition.
    validator = jsonschema.Draft7Validator(schema)
    errors = []

    for error in validator.iter_errors(entry):
        # Create a user-friendly error message
        path = ".".join(str(p) for p in error.absolute_path) or "<root>"
        errors.append(f"Validation error at '{path}': {error.message}")

    is_valid = not errors
    return is_valid, errors
