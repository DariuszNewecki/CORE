# tests/will/autonomy/test_daily_spend_cap.py

"""ADR-172 daily money cap: blocked at/over the cap or on an unpriced call."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.exceptions import GovernanceInstrumentError
from shared.infrastructure.intent.generation_budget import TaskBudget, _parse_budget
from will.autonomy import daily_spend_cap
from will.autonomy.daily_spend_cap import refuse_when_daily_spend_cap_reached
from will.workers.proposal_consumer_worker import _post_spend_cap_reached


_TEST_GEN = [SimpleNamespace(ref_id="flow.build_test_for_symbol")]


def _session(spent: str, unpriced: int) -> MagicMock:
    result = MagicMock()
    result.one.return_value = (Decimal(spent), unpriced)
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    return session


def _cap(value: float | None):
    budget = MagicMock()
    budget.for_task_type.return_value = TaskBudget(5, 600, value)
    return patch.object(daily_spend_cap, "load_generation_budget", return_value=budget)


# ID: 2a6f9c13-8e47-4b05-9d1a-7c3e5b8f0d26
def test_parse_budget_reads_the_cap() -> None:
    assert _parse_budget({"daily_spend_usd_max": 0.05}).daily_spend_usd_max == 0.05
    assert _parse_budget({}).daily_spend_usd_max is None


# ID: 9d4b7e28-1c53-4a6f-8e0b-3f7a2c9d5e14
async def test_under_the_cap_runs() -> None:
    session = _session("0.0400", 0)
    with _cap(0.05):
        await refuse_when_daily_spend_cap_reached(session, _TEST_GEN)
    assert session.execute.await_args.args[1] == {"role": "Coder"}


# ID: 5e8a1f46-3b72-4c9d-a0e5-6d2f8b4c1a37
async def test_at_the_cap_is_blocked() -> None:
    with _cap(0.05), pytest.raises(GovernanceInstrumentError) as exc:
        await refuse_when_daily_spend_cap_reached(_session("0.0500", 0), _TEST_GEN)
    assert exc.value.instrument == "daily_spend_cap"


# ID: 0c3f6a92-7d15-4e8b-b4a1-9e2d5c7f3b68
async def test_an_unpriced_call_counts_as_the_cap() -> None:
    with _cap(0.05), pytest.raises(GovernanceInstrumentError) as exc:
        await refuse_when_daily_spend_cap_reached(_session("0.0010", 1), _TEST_GEN)
    assert "no price" in exc.value.reason


# ID: 8f1e4b37-6a29-4d0c-9b5e-2c7a3f8d1e95
async def test_no_cap_or_other_proposals_are_not_checked() -> None:
    session = _session("9.0", 0)
    with _cap(None):
        await refuse_when_daily_spend_cap_reached(session, _TEST_GEN)
    with _cap(0.05):
        await refuse_when_daily_spend_cap_reached(
            session, [SimpleNamespace(ref_id="fix.imports")]
        )
    session.execute.assert_not_awaited()


# ID: 4b7d2e85-9c31-4f6a-a8e0-1d5c3b9f7a42
async def test_blocked_posts_one_finding_per_day() -> None:
    worker = MagicMock()
    worker.post_finding = AsyncMock()
    await _post_spend_cap_reached(worker, "today's Coder spend USD 0.0500 >= cap")
    kwargs = worker.post_finding.await_args.kwargs
    assert kwargs["subject"].startswith("test_generation.daily_spend_cap_reached::")
    assert kwargs["resolution_mechanism"] == "human"


# ID: 6c9e2a17-4f83-4b5d-a1e0-8d3b7f5c2e96
async def test_an_unreadable_spend_blocks_instead_of_failing() -> None:
    session = MagicMock()
    session.execute = AsyncMock(side_effect=OSError("db down"))
    with _cap(0.05), pytest.raises(GovernanceInstrumentError) as exc:
        await refuse_when_daily_spend_cap_reached(session, _TEST_GEN)
    assert "could not be read" in exc.value.reason
