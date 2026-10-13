# src/shared/infrastructure/intent/vocabulary_projection.py
"""
Vocabulary projection loader (ADR-023 D4).

Sole sanctioned reader of .intent/META/vocabulary.json. Returns one of:

- VocabularyProjection(state="healthy")
- VocabularyProjection(state="drift", drift_detected=True)
- VocabularyProjectionError(state="broken", reason=...)

The loader does not fall back to defaults on broken state — that is
instrument failure and callers must enter governance-DEGRADED mode.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import jsonschema
from jsonschema import Draft7Validator
from referencing import Registry, Resource
from referencing.exceptions import NoSuchResource
from referencing.jsonschema import DRAFT7

from shared.infrastructure.intent._floor import resolve_floor_path
from shared.infrastructure.intent.law_roots import configured_repo_root, law_path
from shared.logger import getLogger


logger = getLogger(__name__)

VOCABULARY_JSON_REL = ".intent/META/vocabulary.json"
VOCABULARY_SCHEMA_REL = ".intent/META/vocabulary.schema.json"


@dataclass(frozen=True)
# ID: 4d8c2e7a-9b3f-4a1c-b6d2-7e8f3c1a5b06
class VocabularyTerm:
    """A single vocabulary entry, projection-shape (frozen)."""

    term: str
    definition: str
    not_: str
    aliases: tuple[str, ...] = ()
    see_also: tuple[str, ...] = ()


@dataclass(frozen=True)
# ID: 6c1f3a8e-2d7b-4f9c-a4e1-8b9c2d5f1e07
class VocabularyProjection:
    """A successfully loaded projection. state is 'healthy' or 'drift'."""

    terms: tuple[VocabularyTerm, ...]
    drift_detected: bool
    state: Literal["healthy", "drift"]
    source_hash: str


@dataclass(frozen=True)
# ID: 8a4d2e6c-1f9b-4c3d-b8e2-5d7f1a4c9e08
class VocabularyProjectionError:
    """A broken projection. Sentinel — not an exception."""

    state: Literal["broken"]
    reason: str


# ID: 9d3a5c1e-7b2f-4a8d-b1c3-4e7f8a2d5c0b
def _validate_schema(instance: dict, schema_path: Path, schema: dict) -> str | None:
    """Validate instance against schema with $ref resolution. Returns error string or None.

    Referenced schemas (e.g. `./enums.json` next to `vocabulary.schema.json`)
    are loaded from disk via the retrieve callback — mirrors the
    fetch-on-demand behaviour the legacy jsonschema.RefResolver had when
    no store was supplied.
    """
    meta_dir = schema_path.parent

    def _retrieve(uri: str) -> Resource:
        name = uri.split("#", 1)[0].rsplit("/", 1)[-1]
        target = meta_dir / name
        if target.is_file():
            return Resource.from_contents(
                json.loads(target.read_text(encoding="utf-8")),
                default_specification=DRAFT7,
            )
        raise NoSuchResource(uri)

    registry = Registry(retrieve=_retrieve)  # type: ignore[call-arg]
    try:
        Draft7Validator(schema, registry=registry).validate(instance)
    except jsonschema.ValidationError as e:
        path = "/".join(str(p) for p in e.absolute_path) or "<root>"
        return f"schema validation failed at {path}: {e.message}"
    return None


# ID: 1b8e4c2f-9a3d-4f7c-b2e8-6c1d4f9a3e0c
def load_vocabulary_projection(
    repo_root: Path | None = None,
) -> VocabularyProjection | VocabularyProjectionError:
    """
    Load and validate the vocabulary projection.

    Returns VocabularyProjection on healthy/drift; VocabularyProjectionError
    on broken (missing file, malformed JSON, schema validation failure, or
    canonical source paper not parseable).
    """
    root = (repo_root or configured_repo_root()).resolve()
    json_path = law_path(root, VOCABULARY_JSON_REL)
    schema_path = law_path(root, VOCABULARY_SCHEMA_REL)

    if not json_path.is_file():
        fallback = resolve_floor_path(VOCABULARY_JSON_REL)
        if fallback is not None:
            json_path = fallback
        else:
            return VocabularyProjectionError(
                state="broken", reason=f"projection missing: {VOCABULARY_JSON_REL}"
            )
    if not schema_path.is_file():
        fallback = resolve_floor_path(VOCABULARY_SCHEMA_REL)
        if fallback is not None:
            schema_path = fallback
        else:
            return VocabularyProjectionError(
                state="broken", reason=f"schema missing: {VOCABULARY_SCHEMA_REL}"
            )

    try:
        instance = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return VocabularyProjectionError(
            state="broken", reason=f"malformed JSON in {VOCABULARY_JSON_REL}: {e.msg}"
        )
    except OSError as e:
        return VocabularyProjectionError(
            state="broken", reason=f"unreadable projection: {e}"
        )

    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return VocabularyProjectionError(
            state="broken", reason=f"unreadable schema: {e}"
        )

    schema_error = _validate_schema(instance, schema_path, schema)
    if schema_error is not None:
        return VocabularyProjectionError(state="broken", reason=schema_error)

    # vocabulary.json is the only vocabulary source (phase 5b retired the
    # canonical paper it was generated from), so there is nothing to drift from.
    drift = False
    stored_hash = instance["metadata"].get("source_hash", "")

    terms = tuple(
        VocabularyTerm(
            term=t["term"],
            definition=t["definition"],
            not_=t["not"],
            aliases=tuple(t.get("aliases") or ()),
            see_also=tuple(t.get("see_also") or ()),
        )
        for t in instance["terms"]
    )

    return VocabularyProjection(
        terms=terms,
        drift_detected=drift,
        state="drift" if drift else "healthy",
        source_hash=stored_hash,
    )
