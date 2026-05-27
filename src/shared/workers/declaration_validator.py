# src/shared/workers/declaration_validator.py

"""
JSONSchema validation for worker YAML declarations.

Validates parsed worker-YAML dicts against `.intent/META/worker.schema.json`
with `$ref` resolution into `.intent/META/enums.json`. Fails closed if
the canonical `worker_phase` subset is missing or empty (closed-enum
discipline, principle 2; issue #460).

Hooked into shared/workers/base.py Worker._load_declaration immediately
after the YAML parses. Workers whose declaration does not pass this
validator have no constitutional standing and refuse to register.
"""

from __future__ import annotations

from pathlib import Path
from threading import RLock
from typing import Any

import jsonschema
from jsonschema import Draft7Validator, RefResolver

from shared.infrastructure.intent.canonical_enums import get_enum_members
from shared.infrastructure.intent.errors import GovernanceError
from shared.logger import getLogger


logger = getLogger(__name__)

_VALIDATOR_CACHE: Draft7Validator | None = None
_LOCK = RLock()


# ID: 935c6c2c-d03b-4e2c-ad06-c3448b37dfc7
def _build_validator() -> Draft7Validator:
    """Construct the cached Draft7Validator with enums.json in its $ref store.

    Asserts (via get_enum_members) that the canonical `worker_phase`
    enum is present and non-empty in enums.json before returning a
    validator. A missing or empty subset is a constitutional gap and
    must not silently permit any phase value.
    """
    from shared.infrastructure.intent.intent_repository import get_intent_repository

    repo = get_intent_repository()
    schema_path = repo.resolve_rel("META/worker.schema.json")
    enums_path = repo.resolve_rel("META/enums.json")

    schema = repo.load_document(schema_path)
    enums = repo.load_document(enums_path)

    Draft7Validator.check_schema(schema)

    base_uri = schema_path.parent.as_uri() + "/"
    resolver = RefResolver(
        base_uri=base_uri,
        referrer=schema,
        store={
            base_uri + "enums.json": enums,
            base_uri + "worker.schema.json": schema,
        },
    )

    # Principle 2: worker_phase must exist and be non-empty before any
    # worker declaration may validate. get_enum_members raises
    # GovernanceError on absent or empty enum.
    get_enum_members("worker_phase")

    return Draft7Validator(schema, resolver=resolver)


# ID: 81144685-8de2-47c0-9dae-41989c75dfd6
def get_worker_validator() -> Draft7Validator:
    """Return the cached worker-declaration validator, building it on first call."""
    global _VALIDATOR_CACHE
    with _LOCK:
        if _VALIDATOR_CACHE is None:
            _VALIDATOR_CACHE = _build_validator()
        return _VALIDATOR_CACHE


# ID: 69fc228e-00b1-414b-b0c9-e15e8720f13b
def reset_worker_validator_cache() -> None:
    """Drop the cached validator. Tests that mutate .intent/META/ must call this."""
    global _VALIDATOR_CACHE
    with _LOCK:
        _VALIDATOR_CACHE = None


# ID: d145fc6a-3789-4dfc-89f7-0ca45cce9cf8
def validate_worker_declaration(
    declaration: dict[str, Any],
    *,
    source: str | Path = "<dict>",
) -> None:
    """Validate a parsed worker declaration against the canonical schema.

    Fails closed on:
      - any JSONSchema violation in the declaration
      - missing or empty `worker_phase` enum in enums.json
      - unresolved `$ref` into enums.json

    Raises GovernanceError describing the first failure encountered.
    Workers without a passing declaration have no constitutional standing.
    """
    try:
        validator = get_worker_validator()
    except GovernanceError:
        raise
    except Exception as e:
        raise GovernanceError(
            f"Failed to construct worker declaration validator: {e}"
        ) from e

    try:
        validator.validate(declaration)
    except jsonschema.ValidationError as e:
        path = "/".join(str(p) for p in e.absolute_path) or "<root>"
        raise GovernanceError(
            f"Worker declaration {source} failed schema validation at {path}: "
            f"{e.message}"
        ) from e
