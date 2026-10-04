# src/cli/commands/inspect/__init__.py
"""Pattern-inspection logic used by ``core-admin admin patterns``.

The ``inspect`` command group that lived here was never registered in
core-admin and was removed with its commands (2026-10-04); inspection runs
through the /v1/status, /decisions, /refusals and /analysis routes.
"""

from __future__ import annotations
