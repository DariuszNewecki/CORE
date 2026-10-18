# src/body/governance/metadata_proof.py
"""
The metadata proof at the write chokepoint.

An action that declares ``ActionImpact.WRITE_METADATA`` may change comments
and docstrings only (metadata.semantic_preservation,
metadata.operations.comment_length_limit). ActionExecutor runs such an action
inside ``metadata_only_scope``; while the scope is active, FileHandler checks
every ``.py`` write and delete against the file's current content with
``verify_metadata_only_diff`` and raises MetadataProofViolationError before
anything lands.

The scope is a ContextVar, so it covers exactly the running action's own
writes -- including nested actions it dispatches (a nested non-metadata
action does not lift it) -- and never another task's concurrent write. It is
not ``governance_token.current_capability``: that names the innermost action,
which would let a metadata-only action write logic through a nested
WRITE_CODE action. Writes that bypass FileHandler (a subprocess) are not
seen; no metadata-only action makes them.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

from shared.exceptions import MetadataProofViolationError
from shared.infrastructure.intent.operational_config import load_operational_config


_metadata_only_action: ContextVar[str | None] = ContextVar(
    "metadata_only_action", default=None
)


@contextmanager
# ID: 61065884-6ff9-4dc8-a74d-a2decf204d2c
def metadata_only_scope(action_id: str) -> Iterator[None]:
    """Hold *action_id*'s writes to metadata-only until the block exits.

    An enclosing scope wins: the outermost metadata-only action is the one
    whose declaration binds every write beneath it.
    """
    if _metadata_only_action.get() is not None:
        yield
        return
    token = _metadata_only_action.set(action_id)
    try:
        yield
    finally:
        _metadata_only_action.reset(token)


# ID: f4739a4a-2ac8-4f6f-a35b-be5780387f29
def check_metadata_write(
    abs_path: Path, rel_path: str, new_content: str | bytes | None
) -> None:
    """Refuse a ``.py`` write (or delete, when *new_content* is None) that is more than metadata.

    No-op outside a metadata-only scope and for non-Python files.
    """
    action_id = _metadata_only_action.get()
    if action_id is None or not rel_path.endswith(".py"):
        return

    from mind.logic.engines.ast_gate.checks.metadata_checks import (
        verify_metadata_only_diff,
    )

    old = (
        abs_path.read_bytes().decode("utf-8", errors="replace")
        if abs_path.is_file()
        else ""
    )
    if new_content is None:
        new = ""
    elif isinstance(new_content, bytes):
        new = new_content.decode("utf-8", errors="replace")
    else:
        new = new_content
    violations = verify_metadata_only_diff(
        old,
        new,
        {
            "max_comment_length": load_operational_config().misc.metadata_max_comment_length
        },
    )
    if violations:
        raise MetadataProofViolationError(action_id, rel_path, violations)
