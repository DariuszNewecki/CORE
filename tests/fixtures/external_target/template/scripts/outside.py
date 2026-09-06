"""A real Python file outside the ratified ``package/`` prefix.

Used by the authority tests to prove the safe auto-approval envelope's
path-prefix boundary refuses a file that is otherwise a perfectly
ordinary, well-formatted Python module.
"""

from __future__ import annotations


def not_authorized() -> str:
    """Return a marker string identifying this file as outside package/."""
    return "outside package/"
