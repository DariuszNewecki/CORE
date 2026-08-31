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

Fixture functions are called via `.__wrapped__` (same pattern as
tests/cli/resources/vectors/test_rebuild.py) to exercise the underlying
logic directly without going through pytest's own fixture injection.
"""

from __future__ import annotations

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
