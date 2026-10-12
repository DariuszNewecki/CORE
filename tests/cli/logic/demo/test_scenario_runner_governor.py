# tests/cli/logic/demo/test_scenario_runner_governor.py
"""The demo's in-process execute call passes the live governor gate.

An in-process ASGI call carries no Unix-socket identity, so require_governor
refuses it; the demo's private app overrides the gate with the demo runner
(ADR-132 D10.11 step 4). Without the override the call is a 403.
"""

from __future__ import annotations

import httpx
from fastapi import FastAPI

from api.dependencies import get_governor, require_governor
from cli.logic.demo import scenario_runner


def _app() -> FastAPI:
    app = FastAPI()

    @app.post("/v1/proposals/{proposal_id}/execute", dependencies=[require_governor])
    async def execute(proposal_id: str) -> dict[str, str]:
        return {"proposal_id": proposal_id}

    return app


async def _post(app: FastAPI) -> int:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://demo") as c:
        return (await c.post("/v1/proposals/p-1/execute")).status_code


async def test_in_process_call_is_refused_without_the_override() -> None:
    assert await _post(_app()) == 403


async def test_the_demo_override_lets_its_own_app_execute() -> None:
    app = _app()
    app.dependency_overrides[get_governor] = scenario_runner._demo_governor
    assert await _post(app) == 200
