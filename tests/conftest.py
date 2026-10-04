# tests/conftest.py
from __future__ import annotations

import asyncio
import functools
import os
import socket
from collections.abc import AsyncGenerator
from urllib.parse import urlparse

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from shared.config import settings
from shared.infrastructure.database import session_manager
from shared.infrastructure.database.session_manager import (
    dispose_all_engines_for_current_loop_only,
    get_session,
)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with get_session() as session:
        yield session


@pytest_asyncio.fixture(autouse=True)
async def _dispose_db_engines_after_each_test() -> AsyncGenerator[None, None]:
    yield
    await dispose_all_engines_for_current_loop_only()


# ADR-016 D3 — TRUNCATE CASCADE between tests for isolation.
#
# Worker-session writes commit outside the test's transaction, so transactional
# rollback cannot undo them. TRUNCATE at the table level works regardless of
# session ownership. Only fires when the DB is reachable — same guard as
# _skip_db_tests_when_unreachable — and, per ADR-157 D3.3, only for tests
# marked `integration`: this fixture ran unconditionally for all 4,071 tests
# whenever the database happened to be reachable, including the ~4,000 that
# never open a session, paying a real TRUNCATE CASCADE round-trip for no
# reason. Tests are now classified (ADR-157 D3.2), so the marker is a
# reliable gate.
@pytest_asyncio.fixture(autouse=True)
async def _truncate_core_tables_between_tests(
    request: pytest.FixtureRequest,
) -> AsyncGenerator[None, None]:
    yield
    if request.node.get_closest_marker("integration") is None:
        return
    reachable, _ = _db_reachability()
    if not reachable:
        return
    # #773 T5.1: a swallowed cleanup failure is never honest — it means the
    # next test runs against unknown, potentially test-polluted state, and
    # the suite reports it as if nothing happened. Let it fail loudly.
    async with get_session() as session:
        # #941: prove identity on this same connection, inside the same
        # transaction as the TRUNCATE, every time — never a cached verdict.
        # A failed identity query propagates, so no TRUNCATE is issued.
        connected = (
            await session.execute(text("SELECT current_database()"))
        ).scalar_one()
        _refuse_unless_test_database(connected, "teardown current_database()")
        # Tables that accumulate during test runs. Config/registry tables
        # (system_config, llm_resources, cognitive_roles) are excluded —
        # tests read them and cleaning them would break subsequent tests.
        # CASCADE propagates to FK-dependent tables (e.g. proposal_consequences
        # from autonomous_proposals).
        await session.execute(
            text(
                "TRUNCATE TABLE "
                "core.blackboard_entries, "
                "core.autonomous_proposals, "
                "core.audit_runs, "
                "core.decision_traces "
                "CASCADE"
            )
        )
        await session.commit()


# --- #941 — integration runs must target `core_test`, by identity ------------
#
# The TRUNCATE above, and the integration tests' own fixture writes, run against
# whatever `settings.DATABASE_URL` resolves to. The live `core` database sits on
# the same host and port as `core_test`, so the reachability probe cannot tell
# them apart — a single wrong character in `.env.test` (#592 was exactly this
# class of failure) would wipe live blackboard and proposal history.
#
# Two checks share one assertion:
# 1. Session preflight (below): before the first integration test's fixtures
#    run, the configured database name AND the connected server's
#    `current_database()` must both be exactly `core_test`. A session-scoped
#    autouse fixture is set up before any narrower-scoped fixture, so a wrong
#    target aborts before any fixture can write.
# 2. Teardown (above): the TRUNCATE re-proves identity on its own connection.
#
# Exact equality, fail closed: #848 (per-xdist-worker databases) must widen
# this deliberately rather than inherit a permissive pattern.
_EXPECTED_TEST_DATABASE = "core_test"


def _refuse_unless_test_database(name: str | None, source: str) -> None:
    if name == _EXPECTED_TEST_DATABASE:
        return
    pytest.exit(
        f"#941: integration tests must run against {_EXPECTED_TEST_DATABASE!r}, "
        f"but {source} reports {name!r} — refusing before any test fixture "
        "writes or any TRUNCATE runs. Check DATABASE_URL in .env.test.",
        returncode=1,
    )


def _configured_database_name() -> str | None:
    if not settings.DATABASE_URL:
        return None
    return make_url(settings.DATABASE_URL).database


async def _connected_database_name() -> str:
    # Own NullPool engine: session_manager caches engines per event loop, and
    # this runs on a throwaway loop before any test loop exists.
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            return (await conn.execute(text("SELECT current_database()"))).scalar_one()
    finally:
        await engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def _require_test_database_identity(request: pytest.FixtureRequest) -> None:
    if not any(
        item.get_closest_marker("integration") is not None
        for item in request.session.items
    ):
        return
    if not settings.DATABASE_URL:
        # No engine can be built at all; the skip/fail fixtures below own
        # the "no database" case. Nothing can be written or truncated.
        return
    _refuse_unless_test_database(_configured_database_name(), "settings.DATABASE_URL")
    reachable, _ = _db_reachability()
    if not reachable:
        return
    _refuse_unless_test_database(
        asyncio.run(_connected_database_name()), "current_database()"
    )


# --- Skip DB-backed tests when the database is unreachable ----------------------
#
# `.env.test` points DATABASE_URL at a LAN Postgres (e.g. 192.168.20.23/core_test).
# That host is reachable from the dev box and the server, but NOT from an external
# CI runner (GitHub-hosted runners cannot route to a private 192.168.x.x address).
# Without a guard, every DB-backed test blocks on asyncpg's connect attempt until
# its timeout fires, repeatedly — turning the smoke suite into a ~50-minute hang.
#
# A test "needs the database" iff it (directly or via a fixture) opens a session
# through `get_session()`, which funnels through `session_manager._get_state()`.
# `_get_state` is resolved via the module global at call time, so monkeypatching it
# here intercepts every caller regardless of how `get_session` was imported. When
# the host is unreachable we raise `pytest.skip()` from that chokepoint, so the test
# is honestly reported as skipped (it did not run) rather than passed or failed.
# Tests that never touch the database are unaffected.


@functools.lru_cache(maxsize=1)
def _db_reachability() -> tuple[bool, str]:
    """Probe the configured DB host once. Returns (reachable, reason_if_not)."""
    url = os.environ.get("DATABASE_URL") or ""
    parsed = urlparse(url)
    host, port = parsed.hostname, parsed.port or 5432
    if not host:
        return False, "DATABASE_URL is not set"
    try:
        with socket.create_connection((host, port), timeout=3.0):
            return True, ""
    except OSError as exc:
        return (
            False,
            f"database host {host}:{port} is unreachable ({exc.__class__.__name__})",
        )


# ADR-157 D3.4 — CORE_UNIT_JOB=1 (set only in core-ci.yml's `hermetic` job,
# which never provisions a database) turns this fixture's skip into a fail.
# A forgotten `integration` marker on a test that genuinely needs the
# database would otherwise show up as a green skip here — indistinguishable
# from the honest local-dev case this fixture also serves — and the
# unit/integration partition ratchet (D3.4) only checks *collection*, not
# whether a collected `unit` test can actually run. This is the runtime
# half of that guarantee.
def _core_unit_job() -> bool:
    return os.environ.get("CORE_UNIT_JOB", "") == "1"


@pytest.fixture(autouse=True)
def _skip_db_tests_when_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    reachable, reason = _db_reachability()
    if reachable:
        return

    def _unreachable(*_args: object, **_kwargs: object) -> None:
        if _core_unit_job():
            pytest.fail(
                f"requires database, but CORE_UNIT_JOB=1 — this job never "
                f"provisions one ({reason}). Add @pytest.mark.integration "
                "(or a module-level `pytestmark = [pytest.mark.integration]`) "
                "if this test genuinely needs the database (ADR-157 D3.4)."
            )
        pytest.skip(f"requires database — {reason}")

    # raising=True: fail loudly if `_get_state` is ever renamed, rather than
    # silently no-op'ing and letting the hang return unnoticed.
    monkeypatch.setattr(session_manager, "_get_state", _unreachable, raising=True)


# ADR-157 D3.3 — a test without `integration` must not touch the database.
#
# Now that TRUNCATE-based isolation above only runs for `integration`-marked
# tests, an unmarked test that opens a real session anyway would silently
# write state with no cleanup guaranteed — exactly the contamination risk a
# reviewer flagged before this landed. While the database is reachable (the
# complement of the skip-fixture above, which handles the unreachable case),
# fail any such test immediately instead of letting it run un-isolated. This
# is a permanent safety net, not just a transitional measurement guard: it
# stays useful for catching a future misclassification any time the suite
# runs with a live database, including local dev.
@pytest.fixture(autouse=True)
def _fail_unmarked_tests_that_touch_db(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    if request.node.get_closest_marker("integration") is not None:
        return
    reachable, _ = _db_reachability()
    if not reachable:
        return

    def _unexpected_db_access(*_args: object, **_kwargs: object) -> None:
        pytest.fail(
            f"{request.node.nodeid} opened a database session without an "
            "`integration` marker. Add @pytest.mark.integration (or a "
            "module-level `pytestmark = [pytest.mark.integration]`) if this "
            "test genuinely needs the database, or remove the DB access if "
            "it doesn't (ADR-157 D3.2/D3.3)."
        )

    monkeypatch.setattr(
        session_manager, "_get_state", _unexpected_db_access, raising=True
    )


# --- #773 T5.1 — explicit CI/release mode: required DB infra must be up ---------
#
# The skip fixture above is the correct, honest behavior for local development:
# a contributor without LAN Postgres access gets a visibly-skipped DB suite, not
# a hang or a false pass. But the same skip, unnoticed, is dishonest in a release
# gate that's supposed to prove the DB-backed test population actually ran —
# "mostly green" would silently mean "the DB tests never executed."
#
# CORE_REQUIRE_DB_TESTS=1 (set only in core-ci.yml's `validate` job, which
# provisions a real ephemeral Postgres via `services:`) makes an unreachable
# database an immediate, whole-session failure instead of a per-test skip. This
# does not touch the skip fixture above or any other pytest skip in the suite —
# it only converts the one specific "DB required but unreachable" case, and only
# when explicitly opted into. Runs once, before any test's own fixtures, so a
# down database aborts fast with one clear message rather than reporting
# hundreds of individually skipped (or, without this, silently-hung) tests.


def _require_db_tests() -> bool:
    return os.environ.get("CORE_REQUIRE_DB_TESTS", "") == "1"


@pytest.fixture(scope="session", autouse=True)
def _require_db_infrastructure_in_release_mode() -> None:
    if not _require_db_tests():
        return
    reachable, reason = _db_reachability()
    if reachable:
        return
    pytest.exit(
        "CORE_REQUIRE_DB_TESTS=1 but the database is unreachable "
        f"({reason}) — refusing to run: a skip here would silently hide "
        "the entire DB-backed test population from this release gate.",
        returncode=1,
    )
