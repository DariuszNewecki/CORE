# tests/cli/test_daemon_discovery_launch.py
"""#898 — daemon discovery and ``implementation.launch: on_demand``.

``cli.commands.daemon.discovery_decision`` is the pure per-declaration
decision the discovery loop and the ``--only`` branch both consume, so the
launch semantics can be pinned without booting the daemon:

- default mode skips an on-demand declaration as a *skip*, never an error
  (the boot ``ERROR … could not instantiate 'goal_execution_worker'`` was
  the symptom in the issue);
- ``--only <stem>`` refuses an on-demand stem naming the launch mode, and
  does so BEFORE the requires_dedicated_process check (the old refusal
  reason "declares requires_dedicated_process=false" was false for it);
- an absent launch key keeps today's behaviour (daemon-hosted).

The real ``.intent/workers/goal_execution_worker.yaml`` is also driven
through the decision so the shipped declaration is pinned, not just a
synthetic one.
"""

from __future__ import annotations

from typing import Any

import pytest
import yaml

from cli.commands.daemon import (
    DISCOVERY_HOST,
    DISCOVERY_REFUSE_INACTIVE,
    DISCOVERY_REFUSE_NOT_HEAVY,
    DISCOVERY_REFUSE_ON_DEMAND,
    DISCOVERY_SKIP_HEAVY,
    DISCOVERY_SKIP_INACTIVE,
    DISCOVERY_SKIP_ON_DEMAND,
    discovery_decision,
)
from shared.infrastructure.intent.canonical_enums import reload_enums_cache
from shared.infrastructure.intent.errors import GovernanceError
from shared.infrastructure.intent.intent_repository import get_intent_repository


@pytest.fixture(autouse=True)
def _reset_enum_cache() -> None:
    reload_enums_cache()
    yield
    reload_enums_cache()


def _decl(
    *, status: str = "active", launch: str | None = None, heavy: bool | None = None
) -> dict[str, Any]:
    impl: dict[str, Any] = {"module": "will.workers.x", "class": "X"}
    if launch is not None:
        impl["launch"] = launch
    if heavy is not None:
        impl["requires_dedicated_process"] = heavy
    return {
        "kind": "worker",
        "metadata": {"id": "workers.x", "status": status},
        "identity": {"uuid": "12345678-1234-1234-1234-123456789012", "class": "acting"},
        "mandate": {"responsibility": "test", "phase": "execution"},
        "implementation": impl,
    }


# --- default mode -----------------------------------------------------------


def test_default_mode_hosts_plain_active_worker() -> None:
    assert discovery_decision(_decl(), only=None) == (DISCOVERY_HOST, "")


def test_default_mode_skips_on_demand_without_error() -> None:
    verdict, detail = discovery_decision(_decl(launch="on_demand"), only=None)
    assert verdict == DISCOVERY_SKIP_ON_DEMAND
    assert "on_demand" in detail


def test_default_mode_skips_inactive() -> None:
    verdict, _ = discovery_decision(_decl(status="paused"), only=None)
    assert verdict == DISCOVERY_SKIP_INACTIVE


def test_default_mode_skips_heavy() -> None:
    verdict, _ = discovery_decision(_decl(heavy=True), only=None)
    assert verdict == DISCOVERY_SKIP_HEAVY


def test_default_mode_on_demand_decided_before_heavy() -> None:
    """Schema forbids this combination; the decision must still be truthful
    if it ever sees one — on-demand is caller-launched regardless of topology."""
    verdict, _ = discovery_decision(_decl(launch="on_demand", heavy=True), only=None)
    assert verdict == DISCOVERY_SKIP_ON_DEMAND


def test_explicit_launch_daemon_is_hosted() -> None:
    assert discovery_decision(_decl(launch="daemon"), only=None)[0] == DISCOVERY_HOST


# --- --only mode ------------------------------------------------------------


def test_only_mode_hosts_active_heavy_daemon_worker() -> None:
    assert discovery_decision(_decl(heavy=True), only="x") == (DISCOVERY_HOST, "")


def test_only_mode_refuses_on_demand_naming_the_launch_mode() -> None:
    verdict, detail = discovery_decision(_decl(launch="on_demand"), only="x")
    assert verdict == DISCOVERY_REFUSE_ON_DEMAND
    assert "launch: on_demand" in detail
    assert "requires_dedicated_process" not in detail


def test_only_mode_on_demand_refused_before_heavy_check() -> None:
    """The old refusal reason ('declares requires_dedicated_process=false')
    must not be produced for an on-demand worker."""
    verdict, _ = discovery_decision(_decl(launch="on_demand", heavy=False), only="x")
    assert verdict == DISCOVERY_REFUSE_ON_DEMAND


def test_only_mode_refuses_not_heavy_with_true_reason() -> None:
    verdict, detail = discovery_decision(_decl(heavy=False), only="x")
    assert verdict == DISCOVERY_REFUSE_NOT_HEAVY
    assert "requires_dedicated_process=false" in detail


def test_only_mode_refuses_inactive() -> None:
    verdict, _ = discovery_decision(_decl(status="paused", heavy=True), only="x")
    assert verdict == DISCOVERY_REFUSE_INACTIVE


# --- fail-closed and the shipped declaration --------------------------------


def test_unknown_launch_value_raises() -> None:
    with pytest.raises(GovernanceError):
        discovery_decision(_decl(launch="cron"), only=None)


def test_shipped_goal_execution_worker_is_skipped_not_hosted() -> None:
    repo = get_intent_repository()
    path = repo.resolve_rel("workers") / "goal_execution_worker.yaml"
    decl = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert discovery_decision(decl, only=None)[0] == DISCOVERY_SKIP_ON_DEMAND
    assert (
        discovery_decision(decl, only="goal_execution_worker")[0]
        == DISCOVERY_REFUSE_ON_DEMAND
    )
