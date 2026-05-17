# src/will/lifecycle/integration_runner.py

"""
Integration runner facade — Will-layer entry point for /v1/integrate
(ADR-054 Phase 1).

Wraps body.project_lifecycle.integration_service.integrate_changes
so the API layer can drive integration without crossing the
architecture.api.no_body_bypass boundary. Will → Body imports are
sanctioned by architecture.will.must_delegate_to_body.
"""

from __future__ import annotations

from body.project_lifecycle.integration_service import (
    IntegrationError,
    integrate_changes,
)
from shared.context import CoreContext
from shared.logger import getLogger


__all__ = ["IntegrationError", "run_integration"]


logger = getLogger(__name__)


# ID: d57572c6-e0a3-4f1e-bda4-73d74e9d3a08
async def run_integration(context: CoreContext, commit_message: str) -> dict:
    """Run the integration workflow and return a structured result.

    Returns dict with keys:
      ok (bool), message (str | None), error (str | None),
      exit_code (int | None).
    `ok=True` means staged changes were committed (or there were
    none); `ok=False` means a workflow step failed.
    """
    try:
        await integrate_changes(context=context, commit_message=commit_message)
        return {
            "ok": True,
            "message": "Integration complete.",
            "error": None,
            "exit_code": 0,
        }
    except IntegrationError as exc:
        logger.warning("integration_runner: integrate_changes raised: %s", exc)
        return {
            "ok": False,
            "message": None,
            "error": str(exc),
            "exit_code": getattr(exc, "exit_code", 1),
        }
