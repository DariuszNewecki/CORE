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
from collections.abc import Iterator
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
    sentinel = (
        "postgresql+asyncpg://sentinelu:sentinelp@sentinel.invalid:5432/sentinel_db"
    )
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


# --- #962: the secrets file reaches Settings, never the process environment ---

_SENTINEL_KEY = "sentinel-master-key-not-a-real-fernet-key"


@pytest.fixture
def secrets_dir() -> Iterator[Path]:
    import shutil
    import tempfile

    base = REPO_ROOT / "var" / "tmp"
    base.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix="secrets-test-", dir=base))
    yield path
    for p in path.iterdir():
        p.chmod(0o600)
    shutil.rmtree(path)


def test_secrets_file_reaches_settings_but_not_child_processes(
    secrets_dir: Path,
) -> None:
    """A value from the secrets file is visible on settings, absent from
    os.environ, and so absent from any process the caller starts. Uses a
    probe key that only the secrets file defines, so the check holds even
    while .env still carries CORE_MASTER_KEY."""
    secrets_file = secrets_dir / "core.env"
    secrets_file.write_text(f"CORE_SECRETS_PROBE={_SENTINEL_KEY}\n")
    result = _run(
        {"CORE_SECRETS_FILE": str(secrets_file)},
        "import os, subprocess, sys\n"
        "from shared.config import settings\n"
        "print(getattr(settings, 'CORE_SECRETS_PROBE', None) == "
        f"{_SENTINEL_KEY!r})\n"
        "print('CORE_SECRETS_PROBE' in os.environ)\n"
        "child = subprocess.run([sys.executable, '-c',"
        " \"import os; print('CORE_SECRETS_PROBE' in os.environ)\"],"
        " capture_output=True, text=True)\n"
        "print(child.stdout.strip())\n",
    )
    assert result.returncode == 0, result.stderr
    on_settings, in_environ, in_child = result.stdout.strip().splitlines()
    assert on_settings == "True"
    assert in_environ == "False"
    assert in_child == "False"


def test_secrets_file_wins_over_environment(secrets_dir: Path) -> None:
    secrets_file = secrets_dir / "core.env"
    secrets_file.write_text(f"CORE_MASTER_KEY={_SENTINEL_KEY}\n")
    result = _run(
        {"CORE_SECRETS_FILE": str(secrets_file), "CORE_MASTER_KEY": "from-env"},
        "from shared.config import settings; print(settings.CORE_MASTER_KEY)",
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == _SENTINEL_KEY


def test_unreadable_secrets_file_is_skipped_not_fatal(secrets_dir: Path) -> None:
    """An account the file is not shared with starts normally, without it."""
    if os.geteuid() == 0:
        pytest.skip("root reads files regardless of mode")
    secrets_file = secrets_dir / "core.env"
    secrets_file.write_text(f"CORE_MASTER_KEY={_SENTINEL_KEY}\n")
    secrets_file.chmod(0o000)
    result = _run(
        {"CORE_SECRETS_FILE": str(secrets_file), "CORE_MASTER_KEY": "from-env"},
        "from shared.config import settings; print(settings.CORE_MASTER_KEY)",
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "from-env"


def test_secrets_locations_are_gitignored() -> None:
    result = subprocess.run(
        ["git", "check-ignore", ".secrets/core.env", ".creds"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.stdout.split() == [".secrets/core.env", ".creds"]
