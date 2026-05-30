# src/shared/infrastructure/intent/operational_mode.py
"""
Operational-mode accessor (ADR-079 D4 placeholder).

The chokepoint reads ``current_mode()`` once per ``check_transaction``
call to decide whether mode-conditional capability entries authorize
a write. The interface this module declares is stable; the implementation
in this file is the **placeholder** ADR-079 D4 documents — env-var
sourced, default-on-uncertainty=`live`.

Issue #492 will replace the body with provenance-guaranteed source
resolution (signed manifest, bootstrap config, conflict-resolution rules).
Consumers depend on the *interface*, not the *implementation* — the
accessor's signature does not change when #492 lands.

Paper §6's "default on uncertainty is *live*" semantics fail closed: a
forged dev signal requires successfully setting ``CORE_OPERATIONAL_MODE``
to the exact string ``"dev"``, not merely being in the absence of
provenance. Any other value — missing, empty, mistyped, mixed-case —
collapses to ``"live"``.
"""

from __future__ import annotations

import os
from typing import Literal

from shared.logger import getLogger


logger = getLogger(__name__)

_MODE_ENV_VAR = "CORE_OPERATIONAL_MODE"
_VALID_MODES: frozenset[str] = frozenset({"dev", "live"})

_first_call_logged = False


# ID: 50389c43-7c80-4e9a-a8cc-01b27535ca8a
def current_mode() -> Literal["dev", "live"]:
    """
    Return the current operational mode.

    Reads ``CORE_OPERATIONAL_MODE``. Returns ``"dev"`` only when the env
    var holds the exact string ``"dev"``; returns ``"live"`` for the
    exact string ``"live"`` and for every other case (missing, empty,
    mistyped) per paper §6.

    Logs at INFO on first call only — the resolved value and the source
    consulted — so the operational signal is observable without
    per-call noise.
    """
    global _first_call_logged
    raw = os.environ.get(_MODE_ENV_VAR)
    if raw in _VALID_MODES:
        resolved: Literal["dev", "live"] = "dev" if raw == "dev" else "live"
        source = _MODE_ENV_VAR
    else:
        resolved = "live"
        source = "default" if raw is None else f"{_MODE_ENV_VAR}=<rejected:{raw!r}>"

    if not _first_call_logged:
        logger.info("Operational mode resolved: %s (source: %s).", resolved, source)
        _first_call_logged = True

    return resolved
