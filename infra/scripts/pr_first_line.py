"""A pull request that changes the host or the assistant's hooks says so first.

Governor 2026-10-15: a merge is the only approval, and core-deploy applies
host setup and ``.claude/`` changes from main by itself. So a pull request
touching the setup scripts, the units, the root-run host scripts or
``infra/claude-hooks/`` must start its description with ``Host change:``,
so the line the governor reads first says what the merge will do as root.

Usage (CI): changed paths on stdin, one per line; the description in the
environment variable PR_BODY. Exit 1 with the reason when the line is missing.
"""

from __future__ import annotations

import os
import sys


MARKER = "Host change:"
# Applied as root or into .claude/ by core-deploy (infra/core-deploy
# HOST_SETUP_PATHS, HOST_SCRIPTS, CLAUDE_SOURCE).
HOST_PATHS = (
    "infra/systemd/",
    "infra/claude-hooks/",
    "infra/core-runtime-setup",
    "infra/core-one-path-setup",
    "infra/core-law-setup",
    "infra/core-deploy",
    "infra/core-pipeline",
    "infra/core-sandbox-check",
)


def host_paths(changed: list[str]) -> list[str]:
    """The changed paths that are host setup or the assistant's hooks."""
    return [
        path
        for path in changed
        if any(path.startswith(p) if p.endswith("/") else path == p for p in HOST_PATHS)
    ]


def problem(changed: list[str], body: str) -> str | None:
    """Why this pull request fails the rule, or None."""
    touched = host_paths(changed)
    if not touched:
        return None
    lines = body.strip().splitlines()
    if lines and lines[0].strip().startswith(MARKER):
        return None
    return (
        f"this pull request changes {', '.join(touched)}; the first line of its "
        f"description must start with '{MARKER}' and say what changes on the host"
    )


def main() -> int:
    changed = [line.strip() for line in sys.stdin if line.strip()]
    reason = problem(changed, os.environ.get("PR_BODY", ""))
    if reason:
        print(f"::error::{reason}")
        return 1
    print("ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
