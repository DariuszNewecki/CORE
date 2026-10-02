# src/cli/route_match.py
"""Pre-bootstrap route matching for ``cli.admin_cli``'s fixed dispatch routes.

``runtime external-verify`` and ``runtime external-run`` are intercepted by
``cli.admin_cli`` before any heavy runtime import executes. Each module
recognizes exactly one fixed two-token route; this builds the matcher so the
prefix test is written once. Stdlib only, no CORE imports — it runs before
anything else in the process has been touched.
"""

from __future__ import annotations

from collections.abc import Callable


# ID: 0d99c4d1-56db-4999-9c7a-5ee6d5488595
def route_matcher(route: tuple[str, str]) -> Callable[[list[str]], bool]:
    """Return ``matches_route(argv)``: True iff ``argv`` (``sys.argv[1:]``)
    starts with exactly the two tokens of ``route``. Pure prefix match — no
    argument parsing."""

    # ID: 7beb68a6-d1c7-4a88-8b90-c3e34f49617c
    def matches_route(argv: list[str]) -> bool:
        return len(argv) >= 2 and tuple(argv[:2]) == route

    return matches_route
