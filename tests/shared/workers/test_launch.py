# tests/shared/workers/test_launch.py
"""Tests for shared.workers.launch.resolve_launch (issue #898).

The resolver is the single source of the daemon | on_demand decision. It
reads ``implementation.launch``, defaults to ``daemon`` when the key is
absent (backward compatibility), and validates against the canonical
``worker_launch`` enum from .intent/META/enums.json — an unknown value is a
GovernanceError, never a silent default.
"""

from __future__ import annotations

from typing import Any

import pytest

from shared.infrastructure.intent.canonical_enums import reload_enums_cache
from shared.infrastructure.intent.errors import GovernanceError
from shared.workers.launch import LAUNCH_DAEMON, LAUNCH_ON_DEMAND, resolve_launch


@pytest.fixture(autouse=True)
def _reset_enum_cache() -> None:
    reload_enums_cache()
    yield
    reload_enums_cache()


def _decl(launch: str | None = None) -> dict[str, Any]:
    impl: dict[str, Any] = {"module": "will.workers.x", "class": "X"}
    if launch is not None:
        impl["launch"] = launch
    return {
        "metadata": {"id": "workers.x", "status": "active"},
        "identity": {"uuid": "12345678-1234-1234-1234-123456789012"},
        "implementation": impl,
    }


def test_absent_launch_resolves_to_daemon() -> None:
    assert resolve_launch(_decl()) == LAUNCH_DAEMON == "daemon"


def test_explicit_daemon_resolves_to_daemon() -> None:
    assert resolve_launch(_decl("daemon")) == LAUNCH_DAEMON


def test_on_demand_resolves_to_on_demand() -> None:
    assert resolve_launch(_decl("on_demand")) == LAUNCH_ON_DEMAND == "on_demand"


def test_unknown_launch_value_raises_governance_error() -> None:
    with pytest.raises(GovernanceError) as excinfo:
        resolve_launch(_decl("cron"))
    msg = str(excinfo.value)
    assert "workers.x" in msg
    assert "'cron'" in msg
    assert "worker_launch" in msg


def test_missing_implementation_block_defaults_to_daemon() -> None:
    """A declaration with no implementation block is a schema problem for the
    validator, not for the resolver — it still resolves to the default."""
    assert resolve_launch({"metadata": {"id": "workers.bare"}}) == LAUNCH_DAEMON


def test_constants_are_members_of_the_canonical_enum() -> None:
    """The two names the runtime branches on must exist in law."""
    from shared.infrastructure.intent.canonical_enums import get_enum_members

    members = get_enum_members("worker_launch")
    assert {LAUNCH_DAEMON, LAUNCH_ON_DEMAND} <= members
