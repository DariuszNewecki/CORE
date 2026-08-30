# tests/shared/test_config_env_precedence.py
"""Regression tests for #845: Settings.__init__ discarding explicit
process-environment DATABASE_URL/CORE_ENV via load_dotenv(override=True).

Subprocess-level, not in-process: `Settings.__init__`'s dotenv cascade is
skipped entirely under pytest (`is_testing` short-circuits it, and
pytest-dotenv loads `.env.test` through a separate mechanism), so the buggy
code path this fix touches is only reachable from a genuinely fresh, non-
pytest process. Each test spawns `python -c` with a controlled environment
and reads back what `shared.config.settings` resolved to.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


def _run(extra_env: dict[str, str], code: str) -> subprocess.CompletedProcess[str]:
    """Spawn a fresh, non-pytest python process with `extra_env` layered on
    top of a stripped copy of this process's environment.

    Strips PYTEST_CURRENT_TEST -- that's what makes Settings.__init__ take
    the non-testing dotenv-cascade branch, exactly like a plain CLI
    invocation would. Also strips CORE_ENV/DATABASE_URL unconditionally: the
    outer pytest run's own Settings() already forced CORE_ENV=TEST (and
    loaded .env.test's DATABASE_URL) into *this* process's os.environ via
    the #592 pytest branch, so a naive copy would leak that into every
    subprocess regardless of what a given test actually wants to preset.
    """
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("PYTEST_CURRENT_TEST", "CORE_ENV", "DATABASE_URL")
    }
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    env.update(extra_env)
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_preset_database_url_is_preserved() -> None:
    """A DATABASE_URL already in the process environment must survive the
    .env/.creds cascade untouched -- not get silently replaced by .env's own
    value."""
    sentinel = "postgresql+asyncpg://sentinelu:sentinelp@sentinel.invalid:5432/sentinel_db"
    result = _run(
        {"DATABASE_URL": sentinel},
        "from shared.config import settings; print(str(settings.DATABASE_URL))",
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == sentinel


def test_preset_core_env_selects_intended_environment() -> None:
    """A preset CORE_ENV=TEST must survive .env's own CORE_ENV="development"
    long enough to be read by _get_env_file_name, so .env.test actually
    loads -- not .env again."""
    result = _run(
        {"CORE_ENV": "TEST"},
        "from shared.config import settings\n"
        "print(settings.CORE_ENV)\n"
        "print('core_test' in str(settings.DATABASE_URL))\n",
    )
    assert result.returncode == 0, result.stderr
    core_env, is_core_test = result.stdout.strip().splitlines()
    assert core_env == "TEST"
    assert is_core_test == "True"


def test_absent_overrides_load_normal_defaults() -> None:
    """With nothing preset, behavior must be unchanged: CORE_ENV always
    defaults to 'development' (Settings' own field default, independent of
    .env). DATABASE_URL's expected value depends on whether a real .env is
    present -- it's gitignored, so a from-scratch clone or CI checkout has
    none, and the fix must not require one to exist; a dev machine with .env
    configured must still see .env's value flow through as a true default."""
    result = _run(
        {},
        "from shared.config import settings\n"
        "print(settings.CORE_ENV)\n"
        "print(str(settings.DATABASE_URL).rsplit('/', 1)[-1])\n",
    )
    assert result.returncode == 0, result.stderr
    core_env, db_name = result.stdout.strip().splitlines()
    assert core_env == "development"
    if (REPO_ROOT / ".env").exists():
        assert db_name == "core"
    else:
        assert db_name == "None"


@pytest.mark.parametrize("core_env_value", ["TEST", "PROD", "PRODUCTION"])
def test_preset_core_env_survives_for_every_named_environment(
    core_env_value: str,
) -> None:
    """Not just TEST -- PROD/PRODUCTION must also survive the .env clobber
    and select their own file per _get_env_file_name's mapping."""
    result = _run(
        {"CORE_ENV": core_env_value},
        "from shared.config import settings; print(settings.CORE_ENV)",
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == core_env_value
