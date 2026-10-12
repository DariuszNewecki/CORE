# tests/api/v1/test_governor_gate_placement.py
"""Which routes need the governor after require_governor went live.

ADR-132 D10.11 step 4: the assistant's producer path (validate, submit,
poll) and the deploy heartbeat stay open; approving, rejecting, executing,
creating proposals and daemon start/stop need the governor.
"""

from __future__ import annotations

import inspect

from fastapi import APIRouter
from fastapi.routing import APIRoute

from api.dependencies import get_governor
from api.v1 import daemon_routes, fix_routes, proposals_routes


def _gated(router: APIRouter) -> dict[tuple[str, str], bool]:
    """(method, path) -> whether the route depends on get_governor, either in
    its decorator or as a parameter default (``user: dict = require_governor``)."""
    table: dict[tuple[str, str], bool] = {}
    for route in router.routes:
        assert isinstance(route, APIRoute)
        in_decorator = any(d.dependency is get_governor for d in route.dependencies)
        in_params = any(
            getattr(p.default, "dependency", None) is get_governor
            for p in inspect.signature(route.endpoint).parameters.values()
        )
        for method in route.methods:
            table[(method, route.path)] = in_decorator or in_params
    return table


def test_proposal_lifecycle_needs_the_governor() -> None:
    table = _gated(proposals_routes.router)
    for path in (
        "/proposals/{proposal_id}/approve",
        "/proposals/{proposal_id}/reject",
        "/proposals/{proposal_id}/execute",
        "/proposals",
    ):
        assert table[("POST", path)], path


def test_producer_submission_and_reads_are_open() -> None:
    table = _gated(proposals_routes.router)
    assert not table[("POST", "/proposals/submit")]
    assert not table[("GET", "/proposals")]
    assert not table[("GET", "/proposals/{proposal_id}")]
    assert not table[("GET", "/proposals/{proposal_id}/chain")]


def test_fix_dry_run_and_status_are_open() -> None:
    table = _gated(fix_routes.router)
    assert not table[("POST", "/fix/run/{fix_id}")]
    assert not table[("GET", "/fix/runs/{run_id}")]


def test_daemon_status_is_open_and_lifecycle_is_gated() -> None:
    assert daemon_routes.ROUTER_EXPOSURE == "user-facing"
    table = _gated(daemon_routes.router)
    assert not table[("GET", "/daemon/status")]
    assert table[("POST", "/daemon/start")]
    assert table[("POST", "/daemon/stop")]


def test_finding_resolve_needs_the_governor() -> None:
    from api.v1 import findings_routes

    table = _gated(findings_routes.router)
    assert table[("POST", "/findings/{entry_id}/resolve")]
