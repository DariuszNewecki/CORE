# tests/shared/infrastructure/test_schema_gate.py
"""ADR-162 D2 — startup schema gate: enforcement semantics and wiring (hermetic).

The per-state verdicts against real databases live in
``migrations/test_schema_gate_postgres.py``. Here ``evaluate_schema_gate`` is
mocked per state and the enforcement contract is checked: every refusing
state raises ``SchemaGateRefusal`` with exit code 78 and the remedy in its
message, ``CURRENT`` and ``DB_UNAVAILABLE`` return, ``CORE_STRICT_MODE`` has
no bearing — and both startup paths (API lifespan, daemon) call the gate,
the daemon converting a refusal into ``typer.Exit(78)`` before it constructs
anything.
"""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, patch

import pytest
import typer

from shared.infrastructure.repositories.db import schema_gate
from shared.infrastructure.repositories.db.schema_gate import (
    EX_CONFIG,
    SchemaGateRefusal,
    SchemaGateState,
    SchemaGateVerdict,
    run_startup_schema_gate,
)


_GATE = "shared.infrastructure.repositories.db.schema_gate.evaluate_schema_gate"


def _verdict(
    state: SchemaGateState, remedy: str | None = "core-admin database migrate --write"
):
    return SchemaGateVerdict(state, f"state={state.value}", remedy=remedy)


@pytest.mark.parametrize(
    "state",
    [
        SchemaGateState.PENDING,
        SchemaGateState.EMPTY_LEDGER,
        SchemaGateState.CONTRADICTION,
        SchemaGateState.NO_SCHEMA,
        SchemaGateState.ASSETS_UNAVAILABLE,
    ],
)
@pytest.mark.parametrize("strict", [True, False])
# ID: b69c716a-baff-45c7-be4a-f6dcfef1d758
async def test_refusing_states_raise_exit_78_regardless_of_strict_mode(
    state: SchemaGateState, strict: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    from shared.config import settings

    monkeypatch.setattr(settings, "CORE_STRICT_MODE", strict, raising=False)
    with (
        patch(_GATE, new=AsyncMock(return_value=_verdict(state))),
        pytest.raises(SchemaGateRefusal) as excinfo,
    ):
        await run_startup_schema_gate("CORE API")
    assert excinfo.value.exit_code == EX_CONFIG == 78
    assert excinfo.value.verdict.state is state
    assert "CORE API refused to start" in str(excinfo.value)
    assert "Run: core-admin database migrate --write" in str(excinfo.value)


@pytest.mark.parametrize(
    "state", [SchemaGateState.CURRENT, SchemaGateState.DB_UNAVAILABLE]
)
# ID: 40022c68-a373-40c5-b81a-4176765cc555
async def test_current_and_unavailable_return_the_verdict(
    state: SchemaGateState,
) -> None:
    with patch(_GATE, new=AsyncMock(return_value=_verdict(state, remedy=None))):
        verdict = await run_startup_schema_gate("CORE daemon")
    assert verdict.state is state and not verdict.refuses


# ID: c355c3b6-143e-4f5f-9eb1-7963411f0de5
def test_every_state_is_classified() -> None:
    refusing = {s for s in SchemaGateState if _verdict(s).refuses}
    assert refusing == {
        SchemaGateState.PENDING,
        SchemaGateState.EMPTY_LEDGER,
        SchemaGateState.CONTRADICTION,
        SchemaGateState.NO_SCHEMA,
        SchemaGateState.ASSETS_UNAVAILABLE,
    }
    assert SchemaGateState.CURRENT not in refusing
    assert SchemaGateState.DB_UNAVAILABLE not in refusing


# ── wiring ───────────────────────────────────────────────────────────────────


# ID: 8cc76416-c985-4b24-aea0-362eb3fac77d
def test_api_lifespan_calls_the_gate_before_warming_services() -> None:
    from body.infrastructure.lifespan import core_lifespan

    source = inspect.getsource(core_lifespan)
    gate_at = source.index('run_startup_schema_gate("CORE API")')
    warm_at = source.index("get_cognitive_service()")
    assert gate_at < warm_at, "the gate must run before any service warms up"
    # Not inside the STRICT_MODE branch: the call is unconditional.
    assert "CORE_STRICT_MODE" not in source[gate_at - 200 : gate_at].split("\n")[-1]


# ID: 4517c1aa-ec12-4e57-b9de-135a5b5a1132
async def test_daemon_refusal_exits_78_before_constructing_anything() -> None:
    from cli.commands import daemon

    refusal = SchemaGateRefusal(_verdict(SchemaGateState.PENDING), "CORE daemon")
    with (
        patch.object(
            schema_gate, "run_startup_schema_gate", new=AsyncMock(side_effect=refusal)
        ),
        patch("shared.infrastructure.git_service.GitService") as git_service,
        pytest.raises(typer.Exit) as excinfo,
    ):
        await daemon._run_daemon_locked()
    assert excinfo.value.exit_code == 78
    git_service.assert_not_called()
