# tests/cli/resources/runtime/test_sandbox_check__socket_option.py
"""sandbox-check does not demand a readable socket path up front.

2026-10-12: Click's Path check refused '/run/core/sandbox.sock' for any
account but core, even for --mode local, which never opens the socket.
"""

from __future__ import annotations

import typer.main

import cli.resources.runtime.sandbox_check  # noqa: F401  (registers the command)
from cli.resources.runtime.health import runtime_app


# ID: 3a9471f4-837f-42cc-8390-2e33e00746ef
def test_socket_option_is_not_checked_for_readability() -> None:
    group = typer.main.get_command(runtime_app)
    command = group.commands["sandbox-check"]  # type: ignore[attr-defined]
    (socket,) = [p for p in command.params if p.name == "socket_path"]
    assert socket.type.readable is False
