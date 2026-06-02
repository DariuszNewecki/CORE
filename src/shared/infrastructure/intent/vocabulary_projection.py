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

import hashlib
import json
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import jsonschema
from jsonschema import RefResolver

from shared.config import resolve_default_repo_path
from shared.logger import getLogger


logger = getLogger(__name__)

CANONICAL_HEADING = "## Canonical Vocabulary (Machine Section)"
VOCABULARY_PAPER_REL = ".specs/papers/CORE-Vocabulary.md"
VOCABULARY_JSON_REL = ".intent/META/vocabulary.json"
VOCABULARY_SCHEMA_REL = ".intent/META/vocabulary.schema.json"


@dataclass(frozen=True)
# ID: 4d8c2e7a-9b3f-4a1c-b6d2-7e8f3c1a5b06
class VocabularyTerm:
    """A single vocabulary entry, projection-shape (frozen)."""

    term: str
    definition: str
    not_: str
    authoritative_paper: str
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


# ID: fcc64fd7-f36e-41b8-be7a-2b1062946287
def normalize_vocabulary_cell(value: str) -> str:
    """
    Produce the identity form of a canonical-vocabulary-table cell.

    The canonical section in CORE-Vocabulary.md is a markdown table; cells
    routinely carry presentation decoration that is not part of the value's
    identity. Today the only such decoration is a surrounding pair of
    backticks (markdown inline-code formatting) around path-shaped cells, plus
    leading/trailing whitespace. Both the sync writer (producing
    vocabulary.json) and the audit gate (validating canonical paths) must
    parse the same identity, so this normalization is the single shared
    contract.

    Behavior: strip leading/trailing whitespace; if the trimmed value is
    wrapped in a single pair of backticks, drop them and strip again.
    """
    v = value.strip()
    if v.startswith("`") and v.endswith("`") and len(v) >= 2:
        return v[1:-1].strip()
    return v


# ID: 3f8c1b4a-7d2e-4f9b-a6c1-9d3e2b5f8a09
def locate_canonical_section(text: str) -> tuple[int, int] | None:
    """
    Return (start_idx, end_idx) of the canonical-section line range, or None.

    The slice text.splitlines()[start_idx:end_idx] spans the heading line
    through the last line before the terminating '---' separator or next
    '## ' heading.
    """
    lines = text.splitlines()
    start = next(
        (i for i, line in enumerate(lines) if line.rstrip() == CANONICAL_HEADING),
        None,
    )
    if start is None:
        return None
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i].strip() == "---" or lines[i].startswith("## "):
            end = i
            break
    return start, end


# ID: 2c9e1f7b-4d8a-4e3c-b9f2-6a8c3e1d4b0a
def compute_canonical_section_hash(repo_root: Path) -> str | None:
    """
    SHA-256 hex of the canonical section in CORE-Vocabulary.md.

    Returns None if the paper is missing or the section heading cannot be
    located. Bytes hashed are exactly text.splitlines()[start:end] joined
    by '\\n', matching the regen command in sync_vocabulary.py.
    """
    paper = repo_root / VOCABULARY_PAPER_REL
    if not paper.is_file():
        return None
    try:
        text = paper.read_text(encoding="utf-8")
    except OSError:
        return None
    rng = locate_canonical_section(text)
    if rng is None:
        return None
    start, end = rng
    section = "\n".join(text.splitlines()[start:end])
    return hashlib.sha256(section.encode("utf-8")).hexdigest()


# ID: 9d3a5c1e-7b2f-4a8d-b1c3-4e7f8a2d5c0b
def _validate_schema(instance: dict, schema_path: Path, schema: dict) -> str | None:
    """Validate instance against schema with $ref resolution. Returns error string or None."""
    base_uri = schema_path.parent.as_uri() + "/"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=DeprecationWarning)
        resolver = RefResolver(base_uri=base_uri, referrer=schema)
        try:
            jsonschema.validate(instance, schema, resolver=resolver)
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
    root = (repo_root or resolve_default_repo_path()).resolve()
    json_path = root / VOCABULARY_JSON_REL
    schema_path = root / VOCABULARY_SCHEMA_REL

    if not json_path.is_file():
        return VocabularyProjectionError(
            state="broken", reason=f"projection missing: {VOCABULARY_JSON_REL}"
        )
    if not schema_path.is_file():
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

    recomputed_hash = compute_canonical_section_hash(root)
    if recomputed_hash is None:
        return VocabularyProjectionError(
            state="broken",
            reason=(
                f"cannot recompute hash: canonical section not found in "
                f"{VOCABULARY_PAPER_REL}"
            ),
        )

    stored_hash = instance["metadata"].get("source_hash", "")
    drift = stored_hash != recomputed_hash

    terms = tuple(
        VocabularyTerm(
            term=t["term"],
            definition=t["definition"],
            not_=t["not"],
            authoritative_paper=t["authoritative_paper"],
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
