# src/cli/pre_bootstrap_git.py
"""Read-only git queries that must run before any CORE bootstrap.

``runtime external-run`` reads the subject's ``HEAD`` and tree before the
environment is bound. At that point no CORE module may be imported: even
``shared.utils.subprocess_utils`` pulls in ``shared.config`` and the
IntentRepository module, which would resolve against the wrong root. So this
one helper calls ``subprocess`` directly. Stdlib only, no CORE imports, like
``cli.route_match``.

It is deliberately the only thing in this module, so the exemption from
``governance.dangerous_execution_primitives`` covers exactly this read and
nothing else. Any git call that runs after bootstrap goes through
``shared.utils.subprocess_utils.run_direct_command`` instead.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


# ID: ff97b3f8-e552-4935-a301-fdbe14b54780
def git_read(path: Path, *args: str) -> str | None:
    """Read-only ``git -C <path> <args>``; None on any failure. Never mutates."""
    try:
        result = subprocess.run(
            ["git", "-C", str(path), *args],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
