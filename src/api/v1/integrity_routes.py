# src/api/v1/integrity_routes.py

"""
Integrity API endpoints (ADR-055 D6 follow-up — closes #353).

Two synchronous endpoints, both filesystem-only:

* POST /integrity/baseline — SHA256-fingerprint src/ and write a
  baseline manifest under var/integrity/. Returns the relative
  manifest path and file count.
* POST /integrity/verify   — diff current src/ against a saved
  baseline. Returns ok / errors / checked_at.

No core.integrity_runs persistence, no BackgroundTasks — operations
are fast (single-digit seconds) and self-contained. Closest precedent
is POST /fix/ir (also synchronous, also no persistence).

CONSTITUTIONAL:
- CoreContext is read from request.app.state.core_context.
- shared.infrastructure.* is reached through the
  will.governance.integrity_runner facade — no direct imports here.
"""

from __future__ import annotations

from fastapi import APIRouter, Body, Request
from pydantic import BaseModel

from shared.context import CoreContext
from shared.logger import getLogger
from will.governance.integrity_runner import (
    create_baseline,
    verify_integrity,
)


logger = getLogger(__name__)


ROUTER_EXPOSURE = "governor-only"
router = APIRouter(
    prefix="/integrity",
    # F-40.1: internal — file-integrity baseline/verify is operator
    # concern, not part of the OEM API contract. Excluded from
    # /v1/openapi.json per ADR-087.
    include_in_schema=False,
)


# ID: f3564baa-a7fb-4c21-a12d-25e06b416ea6
class IntegrityRequest(BaseModel):
    """Body for POST /integrity/baseline and POST /integrity/verify.

    Empty body is valid and equivalent to label='default'.
    """

    label: str = "default"


@router.post("/baseline")
# ID: d93ed634-a710-4e61-ad28-88a5a35e1a0d
async def integrity_baseline(
    request: Request,
    payload: IntegrityRequest = Body(default_factory=IntegrityRequest),
) -> dict:
    """Create a SHA256 baseline of src/ and return path + file count."""
    core_context: CoreContext = request.app.state.core_context
    return create_baseline(core_context, payload.label)


@router.post("/verify")
# ID: 804f2a54-a7c5-4900-afe2-f43e6702a6ee
async def integrity_verify(
    request: Request,
    payload: IntegrityRequest = Body(default_factory=IntegrityRequest),
) -> dict:
    """Verify src/ against the named baseline and return ok / errors."""
    core_context: CoreContext = request.app.state.core_context
    return verify_integrity(core_context, payload.label)
