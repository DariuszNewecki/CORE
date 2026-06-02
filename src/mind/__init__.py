# src/mind/__init__.py
"""
`mind` — Constitutional law and audit governance.

The stateless audit entry point (``run_stateless_audit``) is re-exported
here as the public surface consumed by the F-10.3 GitHub Action wrapper
and any other consumer running CORE's audit without a daemon or
database. Every other symbol in ``mind`` is internal.

Future surface (additional `__all__` entries) is gated on ADR-shaped
promotions per ADR-084 D4 and F-48.4.
"""

from __future__ import annotations

from mind.governance.stateless_audit import run_stateless_audit


__all__ = ["run_stateless_audit"]
