"""Record commands: judge a resolved record against a record catalog (ADR-173)."""

from __future__ import annotations

import typer


app = typer.Typer(
    name="record",
    help="Judge a resolved record (library-snapshot/1) against a record catalog.",
    no_args_is_help=True,
)


@app.callback()
# ID: 8d2f6a1c-3e7b-4c9d-a5f0-1b6e9c2d7a43
def record() -> None:
    """Judge a resolved record (library-snapshot/1) against a record catalog."""


from . import check  # registers the check command on `app`


__all__ = ["app"]
