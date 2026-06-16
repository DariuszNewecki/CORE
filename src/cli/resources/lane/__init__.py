# src/cli/resources/lane/__init__.py
"""Assisted Remediation Lane — external-agent contract (ADR-109, issue #652)."""

from __future__ import annotations

import typer


app = typer.Typer(
    name="lane",
    help="Assisted Remediation Lane: work delegated findings under human-gated approval.",
    no_args_is_help=True,
)

from . import claim as claim_mod
from . import list as list_mod
from . import next as next_mod
from . import propose as propose_mod


app.command("list")(list_mod.list_delegated)
app.command("next")(next_mod.next_finding)
app.command("claim")(claim_mod.claim)
app.command("propose")(propose_mod.propose)

__all__ = ["app"]
