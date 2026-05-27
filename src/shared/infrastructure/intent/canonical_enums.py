# src/shared/infrastructure/intent/canonical_enums.py

"""
Canonical enum store accessor.

Single read-side API for the enum vocabulary declared in
`.intent/META/enums.json`. Consumers MUST NOT inline enum members in
Python or in derived JSON schemas; they reach for `get_enum_members`
instead. Drift between an inlined hardcoded enum and the canonical
store is a governance failure (issue #460).

Fail-closed semantics (closed-enum discipline, principle 2):
- Missing definition  -> GovernanceError
- Missing `enum` key  -> GovernanceError
- Empty `enum` list   -> GovernanceError

Reached via IntentRepository (never direct `Path` reads — CORE rule 6).
Cache is per-process; tests that mutate enums.json must call
`reload_enums_cache()` to drop it.
"""

from __future__ import annotations

from threading import RLock
from typing import Any

from shared.infrastructure.intent.errors import GovernanceError
from shared.logger import getLogger


logger = getLogger(__name__)

_CACHE: dict[str, frozenset[str]] | None = None
_LOCK = RLock()


# ID: a14bddc6-444c-42ad-aea2-9c71fa6de26b
def _load_enums_document() -> dict[str, Any]:
    """Load .intent/META/enums.json through IntentRepository.

    enums.json is part of Bootstrap Contract v0 (see
    `intent_validator._BOOTSTRAP_REQUIRED_FILES`), so by the time any
    caller can reach this code in a daemon context the file is
    guaranteed to exist. A missing file therefore indicates governance
    breakage and propagates as GovernanceError.
    """
    from shared.infrastructure.intent.intent_repository import get_intent_repository

    repo = get_intent_repository()
    path = repo.resolve_rel("META/enums.json")
    doc = repo.load_document(path)
    defs = doc.get("definitions")
    if not isinstance(defs, dict):
        raise GovernanceError(
            f"{path}: missing top-level 'definitions' object — "
            f"enums.json is malformed; canonical enum access cannot proceed."
        )
    return defs


# ID: 88af5df0-1d27-4af3-999b-173478df5f7c
def _populate_cache() -> dict[str, frozenset[str]]:
    defs = _load_enums_document()
    out: dict[str, frozenset[str]] = {}
    for name, schema in defs.items():
        if not isinstance(schema, dict):
            continue
        members = schema.get("enum")
        if isinstance(members, list):
            out[name] = frozenset(str(m) for m in members)
    return out


# ID: b3bae0be-9cf4-4d17-a2c9-690cbcb3fb7a
def get_enum_members(name: str) -> frozenset[str]:
    """Return the canonical members of an enum from .intent/META/enums.json.

    Fail-closed:
      - missing definition  -> GovernanceError
      - missing `enum` key  -> GovernanceError
      - empty `enum` list   -> GovernanceError

    An empty enum means "no value is currently valid"; consumers MUST
    refuse to accept any input rather than silently permit everything.
    """
    global _CACHE
    with _LOCK:
        if _CACHE is None:
            _CACHE = _populate_cache()
        cache = _CACHE

    members = cache.get(name)
    if members is None:
        raise GovernanceError(
            f"canonical enum {name!r} is not declared in .intent/META/enums.json. "
            f"Every consumer-side enum subset must be declared in enums.json before use."
        )
    if not members:
        raise GovernanceError(
            f"canonical enum {name!r} is declared empty in .intent/META/enums.json. "
            f"An empty enum means no value is currently valid; consumers MUST refuse "
            f"to accept any input rather than silently permit everything."
        )
    return members


# ID: 6443e8ab-7103-47d1-9ddf-4c5fa442da26
def reload_enums_cache() -> None:
    """Drop the per-process cache. Re-read on next get_enum_members call.

    Intended for tests that mutate `.intent/META/enums.json` between
    assertions. Daemon code should not call this.
    """
    global _CACHE
    with _LOCK:
        _CACHE = None
