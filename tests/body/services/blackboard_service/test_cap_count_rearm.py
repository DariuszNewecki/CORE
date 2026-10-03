# tests/body/services/blackboard_service/test_cap_count_rearm.py

"""Inherited cap counts re-arm only on a recorded changed condition.

ADR-104 D9 as amended (2026-10-03): an exhausted cap lineage returns to
autonomous eligibility only through governor action on the delegated finding,
ADR-127's clean-pass drain, or rule retirement — never elapsed time or a bare
status change. The three ADR-104 D9 counter-inheritance reads
(query_max_remediation_attempt_count, query_max_attempt_count_by_file_path,
query_max_attempt_count_by_subject) must ignore abandoned rows older than the
latest such event for the same key.

Integration tests against a real Postgres: the predicate is SQL over
payload.resolution, so only executing it proves the behaviour.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy import text

from body.services.blackboard_service.blackboard_query_service import (
    BlackboardQueryService,
)
from body.services.service_registry import service_registry
from shared.infrastructure.database.session_manager import get_session


pytestmark = pytest.mark.integration

_DAY = 86_400
_HOUR = 3_600


@pytest.fixture(autouse=True)
def _prime_service_registry() -> None:
    service_registry.prime(get_session)


@pytest.fixture
async def worker_id():
    wid = uuid.uuid4()
    async with get_session() as session:
        async with session.begin():
            await session.execute(
                text(
                    """
                    INSERT INTO core.worker_registry
                        (worker_uuid, worker_name, worker_class, phase)
                    VALUES (:w, 'test_cap_rearm_worker', 'supervision', 'audit')
                    """
                ),
                {"w": wid},
            )
    yield wid
    async with get_session() as session:
        async with session.begin():
            await session.execute(
                text("DELETE FROM core.blackboard_entries WHERE worker_uuid=:w"),
                {"w": wid},
            )
            await session.execute(
                text("DELETE FROM core.worker_registry WHERE worker_uuid=:w"),
                {"w": wid},
            )


class _Shape:
    """One counter-inheritance read: how its key lands on a row, and the call."""

    def __init__(
        self,
        name: str,
        key_fields: Callable[[str], tuple[str, dict[str, Any]]],
        query: Callable[[BlackboardQueryService, str], Any],
    ) -> None:
        self.name = name
        self.key_fields = key_fields
        self.query = query

    def __repr__(self) -> str:
        return self.name


_SHAPES = [
    _Shape(
        "source_file",
        lambda k: (f"python::test.runner.missing::{k}", {"source_file": k}),
        lambda svc, k: svc.query_max_remediation_attempt_count(k),
    ),
    _Shape(
        "file_path",
        lambda k: (f"python::style.formatter_required::{k}", {"file_path": k}),
        lambda svc, k: svc.query_max_attempt_count_by_file_path(k),
    ),
    _Shape(
        "subject",
        lambda k: (k, {}),
        lambda svc, k: svc.query_max_attempt_count_by_subject(k),
    ),
]


def _key(shape: _Shape) -> str:
    unique = f"src/test_cap_rearm/{uuid.uuid4().hex}.py"
    return f"python::test.rule::{unique}" if shape.name == "subject" else unique


async def _abandoned(worker_id, shape: _Shape, key: str, count: int, age: int) -> None:
    subject, fields = shape.key_fields(key)
    payload = {**fields, "remediation_attempt_count": count}
    await _insert(worker_id, subject, "abandoned", payload, age)


async def _resolved(
    worker_id, shape: _Shape, key: str, resolution: dict | None, age: int
) -> None:
    subject, fields = shape.key_fields(key)
    payload = {**fields, **({"resolution": resolution} if resolution else {})}
    await _insert(worker_id, subject, "resolved", payload, age)


async def _insert(worker_id, subject: str, status: str, payload: dict, age: int):
    async with get_session() as session:
        async with session.begin():
            await session.execute(
                text(
                    """
                    INSERT INTO core.blackboard_entries
                        (id, worker_uuid, entry_type, phase, status, subject,
                         payload, resolution_mechanism, resolved_at, created_at,
                         updated_at, last_seen_at)
                    VALUES
                        (:i, :w, 'finding', 'audit', :st, :s, cast(:p as jsonb),
                         'human',
                         CASE WHEN :st = 'resolved'
                              THEN now() - (:age * interval '1 second') END,
                         now() - (:age * interval '1 second'),
                         now() - (:age * interval '1 second'),
                         now() - (:age * interval '1 second'))
                    """
                ),
                {
                    "i": uuid.uuid4(),
                    "w": worker_id,
                    "st": status,
                    "s": subject,
                    "p": json.dumps(payload),
                    "age": age,
                },
            )


_GOVERNOR = {"resolution_authority": "principal.governor", "resolved_by": "cli_admin"}
_CLEAN_PASS = {
    "resolution_authority": "system.audit",
    "reason": "ADR-127 clean-pass: violation no longer present on re-audit",
}
_RETIRED = {
    "resolution_authority": "system.rule_registry_sweep",
    "resolved_by": "rule_registry_sweep",
}
_TTL_SWEEP = {
    "resolution_authority": "system.ttl_sweep",
    "resolved_by": "blackboard_shop_manager",
}


@pytest.mark.parametrize("shape", _SHAPES, ids=repr)
async def test_no_rearm_event_keeps_all_time_max(worker_id, shape: _Shape) -> None:
    key = _key(shape)
    await _abandoned(worker_id, shape, key, count=3, age=30 * _DAY)
    await _abandoned(worker_id, shape, key, count=1, age=_DAY)
    assert await shape.query(BlackboardQueryService(), key) == 3


@pytest.mark.parametrize("shape", _SHAPES, ids=repr)
async def test_abandoned_rows_older_than_governor_resolution_are_ignored(
    worker_id, shape: _Shape
) -> None:
    key = _key(shape)
    await _abandoned(worker_id, shape, key, count=3, age=_DAY)
    await _resolved(worker_id, shape, key, _GOVERNOR, age=_HOUR)
    assert await shape.query(BlackboardQueryService(), key) == 0
    # A lineage that fails again after the re-arm counts from there.
    await _abandoned(worker_id, shape, key, count=2, age=60)
    assert await shape.query(BlackboardQueryService(), key) == 2


@pytest.mark.parametrize("shape", _SHAPES, ids=repr)
@pytest.mark.parametrize(
    "resolution",
    [_CLEAN_PASS, _RETIRED],
    ids=["clean_pass_drain", "rule_retirement"],
)
async def test_other_recorded_conditions_rearm(
    worker_id, shape: _Shape, resolution: dict
) -> None:
    key = _key(shape)
    await _abandoned(worker_id, shape, key, count=3, age=_DAY)
    await _resolved(worker_id, shape, key, resolution, age=_HOUR)
    assert await shape.query(BlackboardQueryService(), key) == 0


@pytest.mark.parametrize("shape", _SHAPES, ids=repr)
@pytest.mark.parametrize(
    "resolution",
    [None, _TTL_SWEEP],
    ids=["bare_status_change", "ttl_sweep"],
)
async def test_status_change_that_is_not_a_rearm_event_does_not_reset(
    worker_id, shape: _Shape, resolution: dict | None
) -> None:
    key = _key(shape)
    await _abandoned(worker_id, shape, key, count=3, age=_DAY)
    await _resolved(worker_id, shape, key, resolution, age=_HOUR)
    assert await shape.query(BlackboardQueryService(), key) == 3


@pytest.mark.parametrize("shape", _SHAPES, ids=repr)
async def test_rearm_event_on_another_key_does_not_reset(
    worker_id, shape: _Shape
) -> None:
    key, other = _key(shape), _key(shape)
    await _abandoned(worker_id, shape, key, count=3, age=_DAY)
    await _resolved(worker_id, shape, other, _GOVERNOR, age=_HOUR)
    assert await shape.query(BlackboardQueryService(), key) == 3
