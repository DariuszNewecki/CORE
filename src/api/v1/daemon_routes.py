# src/api/v1/daemon_routes.py

"""
Daemon API endpoints (ADR-058 Phase 4, D3).

Three synchronous endpoints; no resource table:

* `GET  /daemon/status` — liveness + per-worker health (ADR-041
  thresholds via `WorkerRegistryService`).
* `POST /daemon/start`  — synchronous `systemctl --user start core-daemon`.
* `POST /daemon/stop`   — returns 200 immediately; the actual
  `systemctl stop` runs as a FastAPI BackgroundTask after the response
  is sent (ADR-058 D3 fire-and-forget pattern).

CONSTITUTIONAL:
- `CoreContext` read from `request.app.state.core_context`.
- `body.services.worker_registry_service` and the subprocess primitive
  are reached through the `will.governance.daemon_runner` facade — no
  direct imports here.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response

from api.dependencies import require_role
from shared.context import CoreContext
from shared.logger import getLogger
from will.governance.daemon_runner import (
    get_status,
    start_daemon,
    stop_daemon_background,
)


logger = getLogger(__name__)


router = APIRouter(
    prefix="/daemon",
    # F-40.1: internal — daemon lifecycle is operator concern, not part
    # of the OEM API contract. Excluded from /v1/openapi.json per ADR-087.
    include_in_schema=False,
    dependencies=[require_role("platform_admin")],
)


@router.get("/status")
# ID: 4a1c8b6d-0f5e-4b3c-8cb9-7ef56789f012
async def daemon_status(request: Request) -> dict:
    """Return current daemon liveness and per-worker health."""
    core_context: CoreContext = request.app.state.core_context
    return await get_status(core_context)


@router.post("/start")
# ID: 5b2d9c7e-1a6f-4c4d-9dca-8f067890a123
async def daemon_start(request: Request) -> dict:
    """Start the core-daemon service via `systemctl --user start`."""
    _ = request
    result = await start_daemon()
    if not result.get("ok", False):
        raise HTTPException(
            status_code=500,
            detail=(
                f"daemon_start_failed: exit_code={result.get('exit_code')}, "
                f"error={result.get('error', 'unknown')}"
            ),
        )
    return {"status": "started", "exit_code": result.get("exit_code", 0)}


@router.post("/stop")
# ID: 6c3e0d8f-2b7a-4d5e-aedb-90178901b234
async def daemon_stop(
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
) -> dict:
    """Signal the daemon to stop (fire-and-forget after 200).

    The response is sent first; `systemctl stop core-daemon` runs as a
    FastAPI BackgroundTask after the response completes. Per ADR-058 D3,
    this preserves correct ordering when the API and daemon share a
    process — and is harmless on deployments where they run as separate
    systemd units (the BackgroundTask still completes cleanly).
    """
    _ = request
    background_tasks.add_task(stop_daemon_background)
    response.status_code = 200
    return {"status": "stopping"}
