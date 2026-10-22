# src/will/autonomy/daily_spend_cap.py
"""
The daily money cap on test generation (ADR-172).

``.intent/enforcement/config/generation_budget.yaml`` sets
``budgets.test_generation.daily_spend_usd_max``. Before a
flow.build_test_for_symbol proposal runs, today's (UTC) spend of the role
test generation calls the model as (``Coder``, var/prompts/
context_aware_test_gen*) is summed from core.llm_exchange_log. At or over
the cap the proposal is blocked, not failed: it stays approved and runs on
a later day, and no symbol attempt is spent. A call logged without a price
today counts as reaching the cap (fail closed). Every Coder call counts,
not only test generation's: the log carries no task link, and counting more
stops earlier, never later.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from shared.exceptions import GovernanceInstrumentError
from shared.infrastructure.intent.generation_budget import load_generation_budget


INSTRUMENT = "daily_spend_cap"
TEST_GEN_FLOW = "flow.build_test_for_symbol"
TEST_GEN_ROLE = "Coder"

_TODAY_SQL = text(
    "SELECT coalesce(sum(cost_estimate), 0), "
    "count(*) FILTER (WHERE cost_estimate IS NULL) "
    "FROM core.llm_exchange_log "
    "WHERE cognitive_role = :role "
    "AND ts >= date_trunc('day', now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC'"
)


# ID: 7e2c4a91-5d38-4b6f-a0e9-3f1b8c6d2a74
def is_test_generation(actions: Any) -> bool:
    """True when any of the proposal's actions is the test-generation flow."""
    return any(getattr(a, "ref_id", None) == TEST_GEN_FLOW for a in actions or [])


# ID: c5a9e3f7-1b62-4d84-9e0a-6f2d7b4c8e13
async def refuse_when_daily_spend_cap_reached(session: Any, actions: Any) -> None:
    """Raise GovernanceInstrumentError when a test-generation proposal would
    run with today's spend at or over the cap. No cap in the law: no check."""
    if not is_test_generation(actions):
        return
    cap = load_generation_budget().for_task_type("test_generation").daily_spend_usd_max
    if cap is None:
        return
    try:
        row = (await session.execute(_TODAY_SQL, {"role": TEST_GEN_ROLE})).one()
        spent, unpriced = float(row[0]), int(row[1])
    except Exception as exc:
        # Fail closed, but blocked rather than failed: a symbol attempt is
        # not spent because today's spend could not be read.
        raise GovernanceInstrumentError(
            instrument=INSTRUMENT,
            reason=f"today's spend could not be read: {type(exc).__name__}: {exc}",
        ) from exc
    if unpriced:
        raise GovernanceInstrumentError(
            instrument=INSTRUMENT,
            reason=(
                f"{unpriced} {TEST_GEN_ROLE} call(s) today have no price; "
                f"counted as the cap (USD {cap:.2f}/day) being reached"
            ),
        )
    if spent >= cap:
        raise GovernanceInstrumentError(
            instrument=INSTRUMENT,
            reason=f"today's {TEST_GEN_ROLE} spend USD {spent:.4f} >= cap USD {cap:.2f}",
        )
