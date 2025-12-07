# src/shared/universal.py
"""
Canonical hub for ultra-reusable micro-helpers.

This module defines the **public, curated surface** of helpers that are truly
universal across the CORE codebase — tiny, pure, side-effect-free utilities
that stabilize patterns and reduce duplication.

Rules for anything placed here:
- MUST be pure (no I/O, no logging, no exceptions for control-flow).
- MUST be simple, composable, and stable.
- MUST NOT depend on ANYTHING outside the `shared/` namespace.
- SHOULD be broadly applicable across features, agents, and governance.
- SHOULD be preferred over re-creating ad-hoc helpers in features/.

This module re-exports helpers defined under `shared.utils.common_knowledge`.
Agents and developers MUST import through `shared.universal` instead of the
implementation module.

Example:
    from shared.universal import normalize_whitespace
"""

from __future__ import annotations

from shared.utils.common_knowledge import (
    collapse_blank_lines,
    ensure_trailing_newline,
    normalize_text,
    normalize_whitespace,
    safe_truncate,
)


__all__ = [
    "normalize_whitespace",
    "normalize_text",
    "collapse_blank_lines",
    "ensure_trailing_newline",
    "safe_truncate",
]
