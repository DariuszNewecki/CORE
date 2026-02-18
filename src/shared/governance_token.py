# src/shared/governance_token.py
"""
Governance Token - The Constitutional ID Badge.

This module manages the ContextVar token that proves an action was authorized
by the ActionExecutor. If this token is not present, atomic actions will refuse to run.
"""

from __future__ import annotations

import contextvars
from collections.abc import Iterator
from contextlib import contextmanager


# The Token. If this is None or empty, the caller is "Unauthorized".
_executor_token = contextvars.ContextVar("executor_token", default=None)


# ID: 7eb1f5ae-8822-4087-afb1-7b10127fb63f
class GovernanceBypassError(RuntimeError):
    """Raised when an atomic action is called directly, bypassing the Executor."""

    pass


@contextmanager
# ID: dd5d8e72-b06a-4875-9b4a-453e33984b17
def authorize_execution(action_id: str) -> Iterator[None]:
    """
    Context manager used ONLY by ActionExecutor to grant temporary authority.
    """
    token = _executor_token.set(action_id)
    try:
        yield
    finally:
        _executor_token.reset(token)


# ID: b2ded143-129c-41fa-8287-92f9bf4b1fdd
def verify_authorization(action_id: str) -> None:
    """
    Called by @atomic_action to ensure the ID badge is present.
    """
    # --- ROOT AUTHORITY EXEMPTION ---
    # The ActionExecutor ('action.execute') is the "Badge Issuer".
    # It cannot hold a badge before it starts, because it creates them.
    # Therefore, it is constitutionally exempt from this check.
    if action_id == "action.execute":
        return
    # --------------------------------

    current_auth = _executor_token.get()

    if current_auth is None:
        raise GovernanceBypassError(
            f"Constitutional Violation: Action '{action_id}' was called directly. "
            "All actions MUST be routed through ActionExecutor.execute()."
        )
