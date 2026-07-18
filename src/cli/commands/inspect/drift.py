# src/cli/commands/inspect/drift.py
"""Guard command registration.

Drift detection lives at `core-admin status drift {symbol|vector}`
(ADR-057 D3) — the `inspect symbol-drift`/`inspect vector-drift`
deprecated aliases that used to forward to it were retired here
(~5.5 months after introduction; no stated CLI deprecation-window
policy, ADR-087 D5's 6-month floor is API-scoped). This module now
only wires guard commands: `register_guard` lives in `cli.commands.guard`
(the local CLI module, not `mind.enforcement.guard_cli` — that import
was a layer inversion).
"""

from __future__ import annotations

import typer

from cli.commands.guard import register_guard


# ID: 7bc2df06-2d2d-47f4-9c61-3e7045009c5a
def register_drift_commands(app: typer.Typer) -> None:
    """Register guard commands.

    Guard commands are registered via cli.commands.guard.register_guard
    (a local CLI module, not the mind-side guard_cli helper). Name
    retained from when this module also registered drift-alias commands.
    """
    register_guard(app)
