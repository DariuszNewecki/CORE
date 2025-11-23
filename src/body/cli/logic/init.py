# src/body/cli/logic/init.py
"""Provides functionality for the init module."""

from __future__ import annotations

import typer

from .init import init_db as _init_db
from .list_audits import list_audits as _list_audits
from .log_audit import log_audit as _log_audit
from .report import report as _report
from .status import _status_impl as _status

app = typer.Typer(help="Generic DB commands (migrations, status, audits).")

# Register commands
app.command("status")(_status)
app.command("init")(_init_db)
app.command("log-audit")(_log_audit)
app.command("list-audits")(_list_audits)
app.command("report")(_report)
