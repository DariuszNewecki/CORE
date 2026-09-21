# src/cli/logging_ui.py
"""
Terminal log rendering for the interactive CLI — and only there.

``shared.logger`` configures a plain, one-line-per-record stderr handler
for every process (journald-honest under systemd). When a human is on
stderr, the CLI may render logs richly; that decision belongs to this
layer (``architecture.channels.cli_rendering_allowed``), never to the
shared logger, which every daemon and API process imports too.

LAYER: cli — Rich imports are permitted here.
"""

from __future__ import annotations

import logging
import os
import sys


# ID: 6fc7ebe9-2a34-4105-b86d-f1dc71964ba0
def install_rich_log_handler() -> bool:
    """Swap the root logger's stderr handler for a RichHandler when stderr
    is a terminal and logs are in human mode.

    Returns True when Rich was installed. Leaves logging untouched under
    systemd, in pipes, and in JSON mode — those keep the shared logger's
    plain handler, whose sd-daemon priority prefix is what makes
    ``journalctl -p err`` truthful. The root level is preserved.
    """
    try:
        is_tty = bool(sys.stderr.isatty())
    except (AttributeError, ValueError):
        is_tty = False
    if not is_tty or os.getenv("LOG_FORMAT_TYPE", "human").lower() == "json":
        return False

    from rich.console import Console
    from rich.logging import RichHandler

    root = logging.getLogger()
    rich_handler = RichHandler(
        console=Console(stderr=True),
        rich_tracebacks=True,
        show_time=True,
        show_level=True,
        show_path=False,
        log_time_format="[%X]",
    )
    rich_handler.setLevel(root.level)
    for handler in list(root.handlers):
        if isinstance(handler, logging.StreamHandler) and getattr(
            handler, "stream", None
        ) in (sys.stderr, sys.__stderr__):
            root.removeHandler(handler)
    root.addHandler(rich_handler)
    return True
