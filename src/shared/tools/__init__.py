# src/shared/tools/__init__.py
"""Shared architectural tools — context builders, anchor generators, vectorizers.

Moved from will.tools per ADR-063 to eliminate the body→will import boundary
violation in body.infrastructure.bootstrap. will.tools re-exports these for
backward compatibility with will-layer callers.
"""

from __future__ import annotations
