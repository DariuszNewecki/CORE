# tests/api/test_dependencies_caller_principal.py
"""get_caller_principal: identity from peer credentials only (ADR-132 D10)."""

from __future__ import annotations

import os
import pwd
from typing import Any

import pytest
from starlette.requests import Request

import api.dependencies as deps
from api.serve import PEER_CRED_EXTENSION
from shared.infrastructure.principal_binding import GOVERNOR, PrincipalBinding


ME = os.getuid()


def _request(
    peer_cred: dict[str, int] | None, headers: list[Any] | None = None
) -> Request:
    scope: dict[str, Any] = {"type": "http", "headers": headers or []}
    if peer_cred is not None:
        scope["extensions"] = {PEER_CRED_EXTENSION: peer_cred}
    return Request(scope)


@pytest.fixture
def governor_binding(monkeypatch: pytest.MonkeyPatch) -> None:
    binding = PrincipalBinding(roles_by_uid={ME: GOVERNOR}, accounts_by_uid={ME: "x"})
    monkeypatch.setattr(deps, "load_principal_binding", lambda: binding)


async def test_bound_unix_caller_is_governor(governor_binding: None) -> None:
    caller = await deps.get_caller_principal(_request({"pid": 1, "uid": ME, "gid": 1}))
    assert caller.uid == ME
    assert caller.account == pwd.getpwuid(ME).pw_name
    assert caller.role == GOVERNOR


async def test_tcp_caller_has_no_identity_even_with_claims(
    governor_binding: None,
) -> None:
    claims = [
        (b"x-core-principal", b"principal.governor"),
        (b"x-uid", str(ME).encode()),
    ]
    caller = await deps.get_caller_principal(_request(None, claims))
    assert caller.uid is None
    assert caller.role is None


async def test_unbound_unix_caller_has_no_role(governor_binding: None) -> None:
    caller = await deps.get_caller_principal(_request({"pid": 1, "uid": 0, "gid": 0}))
    assert caller.uid == 0
    assert caller.role is None


async def test_unavailable_binding_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        deps, "load_principal_binding", lambda: PrincipalBinding(error="missing")
    )
    caller = await deps.get_caller_principal(_request({"pid": 1, "uid": ME, "gid": 1}))
    assert caller.role is None
    assert caller.binding_error == "missing"
