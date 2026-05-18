# src/will/governance/daemon_runner.py

"""
Daemon runner facade — Will-layer entry point for the /daemon API
(ADR-058 D3).

Three synchronous endpoints; no resource table:

* `GET  /daemon/status` — liveness, worker count, per-worker health
  derived from `WorkerRegistryService` (ADR-041 governed thresholds).
* `POST /daemon/start`  — `systemctl --user start core-daemon`.
* `POST /daemon/stop`   — `systemctl --user stop core-daemon` scheduled
  via FastAPI BackgroundTask so the 200 response is sent first
  (ADR-058 D3 fire-and-forget). On this deployment the API and worker
  daemon run as separate systemd units (`core-api.service`,
  `core-daemon.service`), so stop is not technically a self-termination
  — but the BackgroundTask pattern is honoured per ADR for the case
  where the API moves back into the daemon process.
"""

from __future__ import annotations

from typing import Any

from body.services.worker_registry_service import WorkerRegistryService
from shared.context import CoreContext
from shared.infrastructure.intent.operational_config import (
    load_operational_config,
)
from shared.logger import getLogger
from shared.utils.subprocess_utils import run_command_async


__all__ = [
    "get_status",
    "start_daemon",
    "stop_daemon_background",
]


logger = getLogger(__name__)


_SYSTEMCTL_TIMEOUT_SECONDS = 30.0


def _default_alive_threshold_sec() -> int:
    """Governed worker-liveness threshold (ADR-041).

    Falls back to 600 seconds if the operational-config key is absent —
    matches the per-worker default that older entries used pre-ADR-041.
    """
    try:
        cfg = load_operational_config()
        worker_cfg = getattr(cfg, "workers", None)
        if worker_cfg is not None:
            value = getattr(worker_cfg, "alive_threshold_sec", None)
            if value is not None:
                return int(value)
    except Exception as exc:
        logger.debug("daemon_runner: alive threshold lookup failed: %s", exc)
    return 600


# ID: 4e1a8f6b-0d5c-4f2e-a9ba-3c4d5e6f7890
async def get_status(context: CoreContext) -> dict:
    """Return current daemon liveness + per-worker health.

    `context` is accepted for parity with the other Will-layer runners
    but is unused — WorkerRegistryService owns its own session lifecycle.
    """
    _ = context
    threshold = _default_alive_threshold_sec()
    service = WorkerRegistryService()

    try:
        registered = await service.fetch_registered_workers()
    except Exception as exc:
        logger.exception("daemon_runner: fetch_registered_workers failed")
        return {
            "available": False,
            "error": f"{type(exc).__name__}: {exc}",
            "workers": [],
        }

    try:
        alive = await service.fetch_alive_workers(threshold_sec=threshold)
    except Exception as exc:
        logger.warning("daemon_runner: fetch_alive_workers failed: %s", exc)
        alive = []

    alive_uuids = {w.get("uuid") for w in alive}
    workers: list[dict[str, Any]] = []
    for w in registered:
        uuid_val = w.get("uuid")
        workers.append(
            {
                "uuid": str(uuid_val) if uuid_val is not None else None,
                "name": w.get("name"),
                "phase": w.get("phase"),
                "last_heartbeat": (
                    w["last_heartbeat"].isoformat()
                    if w.get("last_heartbeat") is not None
                    else None
                ),
                "alive": uuid_val in alive_uuids,
            }
        )

    return {
        "available": True,
        "alive_threshold_sec": threshold,
        "worker_count": len(workers),
        "alive_count": sum(1 for w in workers if w["alive"]),
        "workers": workers,
    }


# ID: 5f2b9a7c-1e6d-4a3f-bacb-4d5e6f78901a
async def start_daemon() -> dict:
    """Invoke `systemctl --user start core-daemon` synchronously."""
    return await _run_systemctl(("start", "core-daemon"))


# ID: 6a3c0b8d-2f7e-4b4a-cbdc-5e6f7890ab12
async def stop_daemon_background() -> None:
    """Invoke `systemctl --user stop core-daemon` from a BackgroundTask.

    The route handler returns 200 with `{"status": "stopping"}` first,
    then this coroutine runs as a FastAPI BackgroundTask. Errors are
    logged but never raise into the BackgroundTask scheduler.
    """
    try:
        result = await _run_systemctl(("stop", "core-daemon"))
    except Exception as exc:
        logger.exception("daemon_runner: stop_daemon_background raised: %s", exc)
        return
    logger.info("daemon_runner: stop_daemon_background -> %s", result)


# ID: 7b4d1c9e-3a8f-4c5b-dcad-6f7890ab12cd
async def _run_systemctl(argv_tail: tuple[str, ...]) -> dict:
    """Run systemctl --user via the sanctioned subprocess primitive."""
    argv = ["systemctl", "--user", *argv_tail]
    try:
        completed = await run_command_async(argv)
    except FileNotFoundError as exc:
        return {
            "ok": False,
            "exit_code": -1,
            "error": f"systemctl not found: {exc}",
        }
    except Exception as exc:
        return {
            "ok": False,
            "exit_code": -1,
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {
        "ok": completed.returncode == 0,
        "exit_code": completed.returncode,
        "stdout_tail": (completed.stdout or "").splitlines()[-20:],
        "stderr_tail": (completed.stderr or "").splitlines()[-20:],
    }
