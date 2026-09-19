"""ADR-162 U1 -- install-core.sh normalises the database URL scheme.

The bare path used to write the operator's ``--db-url`` into ``.env`` verbatim.
CORE's runtime is async SQLAlchemy + asyncpg and needs ``postgresql+asyncpg://``;
a plain ``postgresql://`` makes the engine import ``psycopg2`` and fail with
``ModuleNotFoundError``. The installer's own ``psql`` calls (libpq) need the
opposite: ``postgresql://`` -- libpq treats ``postgresql+asyncpg://...`` as a
database *name*.

These tests drive the **real** installer (bare and Docker paths) against a
disposable workspace with fake ``poetry`` / ``psql`` / ``python3`` / ``curl`` /
``docker`` on PATH, and assert on what it persists and what it hands to psql.
No database is touched.

Credential hygiene: the fixture password is a sentinel that must never appear
in the installer's output, and assertions are made through pre-computed
booleans (``leaked = SECRET in out; assert not leaked``) so a failing test does
not print the installer output either -- pytest displays the operands of any
expression inside ``assert``.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[2]
INSTALLER = REPO / "install-core.sh"
ENV_EXAMPLE = REPO / ".env.example"

SECRET = "s3cr3t-DO-NOT-LEAK-%40%26"  # contains encoded '@' and '&'
REMAINDER = f"user:{SECRET}@db.internal:5432/core?sslmode=require&application_name=core"
PLAIN_URL = f"postgresql://{REMAINDER}"
ASYNC_URL = f"postgresql+asyncpg://{REMAINDER}"
URLS = {"plain": PLAIN_URL, "asyncpg": ASYNC_URL}
QDRANT = "http://qdrant.internal:6333"
# Parametrised tests take the *key* of URLS, never the URL: pytest prints
# parametrised arguments in test ids and failure headers.

_FAKES: dict[str, str] = {
    # The installer only asks python3 for its version.
    "python3": "#!/bin/bash\necho 3.12\n",
    # `poetry run core-admin database status` is the installer's read-only
    # schema check (U8a); here it reports CURRENT (exit 0) so the U1 tests
    # exercise the "existing current database" branch exactly as before.
    "poetry": "#!/bin/bash\nexit 0\n",
    "curl": "#!/bin/bash\nexit 0\n",
    # Record every argv psql receives (one line per call) so the tests can see
    # which URL form libpq was handed. Never printed by the tests. The `core`
    # namespace probe answers 1 (present), so schema.sql is never loaded.
    "psql": (
        "#!/bin/bash\n"
        'printf "%s\\n" "$1" >> "$PSQL_LOG"\n'
        '[ -n "${PSQL_FAIL:-}" ] && exit 1\n'
        "cat >/dev/null\n"  # swallow a redirected schema.sql
        'if [ "$2" = "-tAc" ]; then echo 1; fi\n'
        "exit 0\n"
    ),
    # Docker path: compose is "ready" immediately, `SELECT 1` answers, and the
    # `core` namespace probe answers 1 (present).
    "docker": (
        "#!/bin/bash\n"
        'case "$*" in\n'
        '  "compose version"|"compose up -d") exit 0 ;;\n'
        '  "compose logs postgres")\n'
        '    printf "PostgreSQL init process complete; ready for start up.\\n"\n'
        '    printf "database system is ready to accept connections\\n"; exit 0 ;;\n'
        "  compose\\ exec*) cat >/dev/null; echo 1; exit 0 ;;\n"
        "  *) exit 1 ;;\n"
        "esac\n"
    ),
}


def _workspace(tmp_path: Path) -> tuple[Path, Path]:
    """Return (workspace, psql_log): a throwaway checkout with fakes on PATH."""
    shim_dir = tmp_path / "bin"
    shim_dir.mkdir(parents=True)
    for name, body in _FAKES.items():
        shim = shim_dir / name
        shim.write_text(body, encoding="utf-8")
        shim.chmod(shim.stat().st_mode | stat.S_IEXEC)

    ws = tmp_path / "workspace"
    ws.mkdir()
    shutil.copy(INSTALLER, ws / "install-core.sh")
    shutil.copy(ENV_EXAMPLE, ws / ".env.example")
    (ws / "schema.sql").write_text(
        "-- empty schema for the installer test\n", encoding="utf-8"
    )
    return ws, tmp_path / "psql.log"


def _run(
    ws: Path, psql_log: Path, *args: str, psql_fail: bool = False
) -> tuple[int, str]:
    env = {
        **os.environ,
        "PATH": os.pathsep.join([str(ws.parent / "bin"), os.environ.get("PATH", "")]),
        "PSQL_LOG": str(psql_log),
        "PSQL_FAIL": "1" if psql_fail else "",
    }
    proc = subprocess.run(
        ["bash", str(ws / "install-core.sh"), *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
        cwd=ws,
    )
    return proc.returncode, proc.stdout + proc.stderr


def _bare(ws: Path, psql_log: Path, db_url: str, **kw: bool) -> tuple[int, str]:
    return _run(
        ws, psql_log, "--bare", "--db-url", db_url, "--qdrant-url", QDRANT, **kw
    )


def _env_value(ws: Path, name: str) -> str | None:
    for line in (ws / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{name}="):
            return line[len(name) + 1 :]
    return None


def _psql_urls(psql_log: Path) -> list[str]:
    return (
        psql_log.read_text(encoding="utf-8").splitlines() if psql_log.exists() else []
    )


# ── the confirmed defect ─────────────────────────────────────────────────────


# ID: d2f13609-4c3e-4b1e-bf64-ee6a9ee0a4fd
def test_plain_postgresql_url_is_persisted_as_asyncpg(tmp_path: Path) -> None:
    ws, log = _workspace(tmp_path)
    code, out = _bare(ws, log, PLAIN_URL)
    assert code == 0, "bare install did not succeed (output redacted)"
    persisted_is_async = _env_value(ws, "DATABASE_URL") == ASYNC_URL
    assert persisted_is_async, (
        "DATABASE_URL in .env is not the postgresql+asyncpg:// form"
    )
    leaked = SECRET in out
    assert not leaked, "installer output contains the credential"


# ID: 1b54a14f-cffe-4c35-9efa-2d40710c7d7b
def test_asyncpg_url_is_persisted_unchanged(tmp_path: Path) -> None:
    ws, log = _workspace(tmp_path)
    code, _ = _bare(ws, log, ASYNC_URL)
    assert code == 0
    unchanged = _env_value(ws, "DATABASE_URL") == ASYNC_URL
    assert unchanged, "a postgresql+asyncpg:// URL must be persisted byte-for-byte"


# ID: 5df4db41-faa3-4801-9e54-cc69ee0c4fa0
@pytest.mark.parametrize("form", ["plain", "asyncpg"])
def test_remainder_including_query_and_encoded_credentials_is_preserved(
    tmp_path: Path, form: str
) -> None:
    """Only the scheme prefix changes. The fixture's remainder carries an
    encoded '@' and '&' in the password and a two-parameter query string --
    the latter is exactly what a sed replacement (the old mechanism) corrupts."""
    ws, log = _workspace(tmp_path)
    assert _bare(ws, log, URLS[form])[0] == 0
    persisted = _env_value(ws, "DATABASE_URL") or ""
    remainder_intact = persisted.split("://", 1)[1:] == [REMAINDER]
    assert remainder_intact, "bytes after :// were altered on persistence"


# ID: 54e7d380-1b35-4d5f-a10d-487007f0d5bc
def test_normalisation_is_idempotent_through_the_real_path(tmp_path: Path) -> None:
    """Feeding the persisted output back in as input yields the same output."""
    ws1, log1 = _workspace(tmp_path / "first")
    assert _bare(ws1, log1, PLAIN_URL)[0] == 0
    once = _env_value(ws1, "DATABASE_URL") or ""

    ws2, log2 = _workspace(tmp_path / "second")
    assert _bare(ws2, log2, once)[0] == 0
    twice = _env_value(ws2, "DATABASE_URL") or ""

    stable = once == twice and once.startswith("postgresql+asyncpg://")
    assert stable, "second normalisation pass changed the URL"


# ── the sync consumer keeps a libpq-compatible scheme ────────────────────────


# ID: 504b3cd5-6b4a-4c0a-9efb-03d70c8c6b2e
@pytest.mark.parametrize("form", ["plain", "asyncpg"])
def test_psql_always_receives_the_libpq_form(tmp_path: Path, form: str) -> None:
    """libpq does not understand postgresql+asyncpg://, so whichever form the
    operator supplies, psql (connectivity check + schema gate + apply) is
    handed postgresql:// with the remainder untouched."""
    ws, log = _workspace(tmp_path)
    assert _bare(ws, log, URLS[form])[0] == 0
    urls = _psql_urls(log)
    assert len(urls) == 2  # connectivity check + `core` namespace probe (present)
    all_libpq = all(u == PLAIN_URL for u in urls)
    assert all_libpq, "psql was handed a URL that is not the plain postgresql:// form"


# ── credential hygiene ───────────────────────────────────────────────────────


# ID: 7dfb5198-4979-4f01-846a-aebfad3f70c5
@pytest.mark.parametrize("form", ["plain", "asyncpg"])
def test_installer_output_never_contains_the_credential(
    tmp_path: Path, form: str
) -> None:
    ws, log = _workspace(tmp_path)
    _, ok_out = _bare(ws, log, URLS[form])
    leaked = SECRET in ok_out
    assert not leaked, "successful install output contains the credential"

    ws_f, log_f = _workspace(tmp_path / "failing")
    code, fail_out = _bare(ws_f, log_f, URLS[form], psql_fail=True)
    assert code == 1
    seen = "Cannot connect to the database" in fail_out
    assert seen, "connectivity failure not reported"
    leaked = SECRET in fail_out
    assert not leaked, "the connectivity error echoed the --db-url"


# ── preserved behaviour ──────────────────────────────────────────────────────


# ID: 5f97f383-c365-4db6-9c78-9aa5ac192124
def test_other_schemes_pass_through_unchanged(tmp_path: Path) -> None:
    """U1 rewrites only the postgresql:// prefix. ``postgres://`` (accepted by
    libpq, rejected by SQLAlchemy) is passed through exactly as before -- the
    installer does not invent support for it (ADR-162 D10 scope)."""
    url = f"postgres://{REMAINDER}"
    ws, log = _workspace(tmp_path)
    assert _bare(ws, log, url)[0] == 0
    untouched = _env_value(ws, "DATABASE_URL") == url and _psql_urls(log) == [url, url]
    assert untouched, "a non-postgresql:// scheme was rewritten"


# ID: 324917d5-9da6-41e1-8777-29a3d5fb66ca
def test_bare_path_behaviour_outside_the_url_is_unchanged(tmp_path: Path) -> None:
    ws, log = _workspace(tmp_path)
    code, out = _bare(ws, log, PLAIN_URL)
    assert code == 0
    # .env is .env.example with exactly the two operator lines replaced.
    expected = [
        f"QDRANT_URL={QDRANT}"
        if line.startswith("QDRANT_URL=")
        else f"DATABASE_URL={ASYNC_URL}"
        if line.startswith("DATABASE_URL=")
        else line
        for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines()
    ]
    env_matches = (ws / ".env").read_text(encoding="utf-8").splitlines() == expected
    assert env_matches, ".env differs from .env.example beyond the two operator lines"
    assert not list(ws.glob(".env.tmp.*")), "temporary .env file left behind"
    # The rest of the bare path still runs.
    for script in ("start.sh", "stop.sh"):
        assert (ws / script).exists() and os.access(ws / script, os.X_OK)
    seen = "a CORE schema is present" in out and "database is current" in out
    assert seen
    assert (ws / "var" / "run").is_dir() and (ws / "var" / "logs").is_dir()


# ID: 709f76f7-62d9-445c-a21d-4680e8a4eda6
def test_existing_env_is_left_untouched(tmp_path: Path) -> None:
    ws, log = _workspace(tmp_path)
    (ws / ".env").write_text("DATABASE_URL=keep-me\n", encoding="utf-8")
    code, out = _bare(ws, log, PLAIN_URL)
    assert code == 0
    seen = ".env already exists" in out
    assert seen
    assert (ws / ".env").read_text(encoding="utf-8") == "DATABASE_URL=keep-me\n"


# ID: c742933d-8778-4e48-8d03-7c2e541653f4
def test_docker_path_persists_env_example_verbatim(tmp_path: Path) -> None:
    """The Docker path takes no --db-url; .env is .env.example byte-for-byte
    (whose DATABASE_URL already carries the asyncpg scheme)."""
    ws, log = _workspace(tmp_path)
    code, out = _run(ws, log)
    assert code == 0, "docker install did not succeed"
    assert (ws / ".env").read_bytes() == ENV_EXAMPLE.read_bytes()
    assert (_env_value(ws, "DATABASE_URL") or "").startswith("postgresql+asyncpg://")
    assert _psql_urls(log) == []  # the Docker path never calls psql directly
    seen = "CORE is installed and running" in out
    assert seen


# ID: aa0a4f03-c9e5-4c30-8809-f49322f5bfb8
def test_help_advertises_the_async_form() -> None:
    proc = subprocess.run(
        ["bash", str(INSTALLER), "--help"], capture_output=True, text=True, check=False
    )
    assert proc.returncode == 0
    assert '--db-url  "postgresql+asyncpg://' in proc.stdout
    assert "postgresql://user:pass" not in proc.stdout
