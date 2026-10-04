"""Regression tests for #773 T5.1 — honest DB-suite skip vs. release-mode gate.

Two behaviors under test, both in tests/conftest.py:

1. Developer mode (default, CORE_REQUIRE_DB_TESTS unset): an unreachable
   database still produces a visible pytest skip via the pre-existing
   `_skip_db_tests_when_unreachable` fixture -- unchanged by this work,
   verified here only at the `_require_db_tests()` flag-reading level.
2. Release mode (CORE_REQUIRE_DB_TESTS=1): an unreachable database aborts
   the whole session via `pytest.exit` instead of silently skipping the
   entire DB-backed test population. Wired into core-ci.yml's `validate`
   job only, which provisions a real ephemeral Postgres.

Also covers the removed `except Exception: pass` in the between-test
truncate-cleanup fixture: a cleanup failure now propagates instead of
being swallowed.

3. ADR-157 D3.4 — CORE_UNIT_JOB=1 (set only in core-ci.yml's `hermetic`
   job, which never provisions a database) turns the same unreachable-DB
   case that (1) skips on into a hard failure instead, so a forgotten
   `integration` marker on a test that needs the database can't show up
   as a green skip in the one job where DB is never even attempted.

4. #941 — integration runs must target `core_test` by identity: a session
   preflight refuses a wrong configured or connected database name before
   any test fixture can write, and the TRUNCATE teardown re-proves identity
   on its own connection, issuing no TRUNCATE and no commit on mismatch.

Fixture functions are called via `.__wrapped__` (same pattern as
tests/cli/resources/vectors/test_rebuild.py) to exercise the underlying
logic directly without going through pytest's own fixture injection.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import tests.conftest as conftest_module


def test_require_db_tests_false_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CORE_REQUIRE_DB_TESTS", raising=False)
    assert conftest_module._require_db_tests() is False


def test_require_db_tests_true_when_set_to_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CORE_REQUIRE_DB_TESTS", "1")
    assert conftest_module._require_db_tests() is True


def test_require_db_tests_false_for_other_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for value in ("0", "true", "yes", ""):
        monkeypatch.setenv("CORE_REQUIRE_DB_TESTS", value)
        assert conftest_module._require_db_tests() is False, value


def test_release_mode_off_never_exits_regardless_of_reachability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Developer mode (flag unset) is completely unaffected by this fixture,
    even when the database is unreachable -- that case is the pre-existing
    per-test skip fixture's job, not this one's."""
    monkeypatch.setattr(conftest_module, "_require_db_tests", lambda: False)
    monkeypatch.setattr(
        conftest_module, "_db_reachability", lambda: (False, "unreachable")
    )
    # Must not raise.
    conftest_module._require_db_infrastructure_in_release_mode.__wrapped__()


def test_release_mode_on_and_db_reachable_does_not_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(conftest_module, "_require_db_tests", lambda: True)
    monkeypatch.setattr(conftest_module, "_db_reachability", lambda: (True, ""))
    conftest_module._require_db_infrastructure_in_release_mode.__wrapped__()


def test_release_mode_on_and_db_unreachable_aborts_the_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The #773 T5.1 core case: CORE_REQUIRE_DB_TESTS=1 + unreachable DB must
    fail the whole run via pytest.exit, not skip."""
    monkeypatch.setattr(conftest_module, "_require_db_tests", lambda: True)
    monkeypatch.setattr(
        conftest_module,
        "_db_reachability",
        lambda: (
            False,
            "database host db:5432 is unreachable (ConnectionRefusedError)",
        ),
    )
    with pytest.raises(pytest.exit.Exception) as exc_info:
        conftest_module._require_db_infrastructure_in_release_mode.__wrapped__()
    message = str(exc_info.value)
    assert "CORE_REQUIRE_DB_TESTS=1" in message
    assert "unreachable" in message
    assert "database host db:5432" in message


async def test_truncate_cleanup_failure_propagates_instead_of_being_swallowed() -> None:
    """#773 T5.1: the old `except Exception: pass` masked cleanup failures.
    A truncate failure must now surface as a real fixture-teardown error.

    Uses a scoped MonkeyPatch context (not the function-parameter fixture)
    so the patch is reverted before this test function returns -- this
    file's own ambient, real `_truncate_core_tables_between_tests` autouse
    fixture instance (the one pytest itself invokes for this test) must
    still see the real get_session/_db_reachability at its own teardown,
    not this test's fake exploding session.

    ADR-157 D3.3: the fixture now takes `request` and gates on the
    `integration` marker, so this direct `.__wrapped__()` call needs a
    fake request whose node reports as `integration`-marked -- otherwise
    the fixture would return early before ever reaching the truncate
    logic this test exists to exercise.
    """

    class _ExplodingSession:
        async def __aenter__(self) -> _ExplodingSession:
            return self

        async def __aexit__(self, *exc_info: object) -> None:
            return None

        async def execute(self, *args: object, **kwargs: object) -> None:
            raise RuntimeError("simulated truncate failure")

        async def commit(self) -> None:
            raise AssertionError("commit should not be reached after execute fails")

    def _fake_get_session() -> _ExplodingSession:
        return _ExplodingSession()

    fake_request = MagicMock()
    fake_request.node.get_closest_marker.return_value = (
        MagicMock()
    )  # non-None => "integration"-marked

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(conftest_module, "_db_reachability", lambda: (True, ""))
        mp.setattr(conftest_module, "get_session", _fake_get_session)

        gen = conftest_module._truncate_core_tables_between_tests.__wrapped__(
            fake_request
        )
        await anext(gen)  # advance to the fixture's `yield`
        with pytest.raises(RuntimeError, match="simulated truncate failure"):
            await anext(gen)  # drives the post-yield cleanup code


async def test_unreachable_db_without_unit_job_flag_still_skips(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ADR-157 D3.4: CORE_UNIT_JOB unset (or not '1') preserves the
    pre-existing honest-skip behavior -- a contributor without a local
    database still gets a visible skip, not a failure."""
    monkeypatch.delenv("CORE_UNIT_JOB", raising=False)
    monkeypatch.setattr(
        conftest_module, "_db_reachability", lambda: (False, "unreachable")
    )
    conftest_module._skip_db_tests_when_unreachable.__wrapped__(monkeypatch)
    with pytest.raises(pytest.skip.Exception):
        async with conftest_module.get_session():
            pass


async def test_unreachable_db_with_unit_job_flag_fails_instead_of_skipping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ADR-157 D3.4: CORE_UNIT_JOB=1 turns the same unreachable-DB case into
    a hard failure. The `hermetic` job never provisions a database, so a
    green skip there would be indistinguishable from a forgotten
    `integration` marker on a test that genuinely needs one."""
    monkeypatch.setenv("CORE_UNIT_JOB", "1")
    monkeypatch.setattr(
        conftest_module, "_db_reachability", lambda: (False, "unreachable")
    )
    conftest_module._skip_db_tests_when_unreachable.__wrapped__(monkeypatch)
    with pytest.raises(pytest.fail.Exception):
        async with conftest_module.get_session():
            pass


# --- #941 — database identity guard -------------------------------------------


class _IdentitySession:
    """Fake session: answers `current_database()` with `name`, records the rest."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.statements: list[str] = []
        self.commits = 0

    async def __aenter__(self) -> _IdentitySession:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        return None

    async def execute(self, statement: object, *args: object, **kwargs: object):
        sql = str(statement)
        self.statements.append(sql)
        result = MagicMock()
        result.scalar_one.return_value = self.name
        return result

    async def commit(self) -> None:
        self.commits += 1


async def _drive_teardown(session: _IdentitySession) -> None:
    fake_request = MagicMock()
    fake_request.node.get_closest_marker.return_value = MagicMock()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(conftest_module, "_db_reachability", lambda: (True, ""))
        mp.setattr(conftest_module, "get_session", lambda: session)
        gen = conftest_module._truncate_core_tables_between_tests.__wrapped__(
            fake_request
        )
        await anext(gen)
        with pytest.raises(StopAsyncIteration):
            await anext(gen)


async def test_teardown_wrong_database_issues_no_truncate_and_no_commit() -> None:
    session = _IdentitySession("core")
    with pytest.raises(pytest.exit.Exception, match="'core'"):
        await _drive_teardown(session)
    assert not any("TRUNCATE" in sql for sql in session.statements)
    assert session.commits == 0


async def test_teardown_core_test_still_truncates_after_identity_check() -> None:
    session = _IdentitySession("core_test")
    await _drive_teardown(session)
    assert "current_database()" in session.statements[0]
    assert "TRUNCATE" in session.statements[1]
    assert session.commits == 1


def _items(*integration: bool) -> MagicMock:
    request = MagicMock()
    request.session.items = [
        MagicMock(get_closest_marker=MagicMock(return_value=MagicMock() if i else None))
        for i in integration
    ]
    return request


def _patch_database_url(mp: pytest.MonkeyPatch, database: str) -> None:
    mp.setattr(
        conftest_module.settings,
        "DATABASE_URL",
        f"postgresql+asyncpg://u:p@127.0.0.1:5432/{database}",
    )


def test_preflight_ignores_unit_only_runs() -> None:
    with pytest.MonkeyPatch.context() as mp:
        _patch_database_url(mp, "core")
        conftest_module._require_test_database_identity.__wrapped__(
            _items(False, False)
        )


def test_preflight_refuses_wrong_configured_name_before_connecting() -> None:
    def _must_not_connect() -> tuple[bool, str]:
        raise AssertionError("preflight probed the server before the name check")

    with pytest.MonkeyPatch.context() as mp:
        _patch_database_url(mp, "core")
        mp.setattr(conftest_module, "_db_reachability", _must_not_connect)
        with pytest.raises(pytest.exit.Exception, match=r"settings\.DATABASE_URL"):
            conftest_module._require_test_database_identity.__wrapped__(
                _items(False, True)
            )


def test_preflight_refuses_wrong_connected_name() -> None:
    """Configured name is right but the server says otherwise (alias, proxy)."""

    async def _connected() -> str:
        return "core"

    with pytest.MonkeyPatch.context() as mp:
        _patch_database_url(mp, "core_test")
        mp.setattr(conftest_module, "_db_reachability", lambda: (True, ""))
        mp.setattr(conftest_module, "_connected_database_name", _connected)
        with pytest.raises(pytest.exit.Exception, match="current_database"):
            conftest_module._require_test_database_identity.__wrapped__(_items(True))


def test_preflight_accepts_core_test_and_defers_unreachable_to_skip_fixture() -> None:
    async def _connected() -> str:
        raise AssertionError("must not connect when unreachable")

    with pytest.MonkeyPatch.context() as mp:
        _patch_database_url(mp, "core_test")
        mp.setattr(conftest_module, "_db_reachability", lambda: (False, "down"))
        mp.setattr(conftest_module, "_connected_database_name", _connected)
        conftest_module._require_test_database_identity.__wrapped__(_items(True))


def test_wrong_env_target_aborts_real_run_before_any_test_body() -> None:
    """End to end through the real root conftest: a child pytest run whose
    DATABASE_URL names a non-`core_test` database exits non-zero with the
    #941 refusal, and its integration test never runs. The probe database
    does not exist, so even a broken guard could not touch live data."""
    repo_root = Path(__file__).resolve().parents[1]
    env = dict(os.environ)
    env["CORE_DB_IDENTITY_PROBE_DATABASE"] = "core_guard_probe_941"
    env["PYTHONPATH"] = os.pathsep.join(
        filter(None, [str(repo_root), env.get("PYTHONPATH")])
    )
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_smoke_db.py",
            "-p",
            "tests.helpers.db_identity_probe_plugin",
            "-p",
            "no:cacheprovider",
            "--no-cov",
            "-q",
        ],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    output = proc.stdout + proc.stderr
    assert proc.returncode == 1, output
    assert "#941" in output and "core_guard_probe_941" in output, output
    assert "passed" not in output and "PASSED" not in output, output
