"""#1374 -- install-core.sh sets up the models and the master key.

Before #1374 the installer told a newcomer to "configure an LLM in .env",
which CORE never read: no install could reach a working model by following
the docs. Now the installer creates CORE_MASTER_KEY in an owner-only
.secrets/core.env and, once the API is up, runs
`core-admin llm-resources setup --write` against Ollama (or the server named
with --llm-url). A missing server or model never fails the install; it is
reported with the exact command that fixes it.

Driven like test_install_core_schema_gate.py: the real installer, with fake
poetry / psql / docker / curl / python3 that record every call.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
SETUP = "run core-admin llm-resources setup --write"

# FAKE_TAGS: what `curl <server>/api/tags` prints; "DOWN" makes curl fail.
# FAKE_SETUP_RC: exit code of `core-admin llm-resources setup --write`.
_FAKES: dict[str, str] = {
    "python3": "#!/bin/bash\necho 3.12\n",
    "curl": (
        "#!/bin/bash\n"
        'case "$*" in\n'
        '  */api/tags*) [ "$FAKE_TAGS" = DOWN ] && exit 7; printf "%s" "$FAKE_TAGS"; exit 0 ;;\n'
        "  *) exit 0 ;;\n"
        "esac\n"
    ),
    "poetry": (
        "#!/bin/bash\n"
        'printf "%s\\n" "$*" >> "$CALL_LOG"\n'
        'case "$*" in\n'
        '  "run core-admin code audit"*)\n'
        '    printf \'{"verdict":"DEGRADED","findings":[],"stats":{"skipped_blocking_rule_ids":["a.b"]}}\'; exit 1 ;;\n'
        '  "run core-admin llm-resources setup"*) exit "${FAKE_SETUP_RC:-0}" ;;\n'
        '  "run python -"*) shift 2; exec "$REAL_PYTHON" "$@" ;;\n'
        "  *) exit 0 ;;\n"
        "esac\n"
    ),
    "psql": "#!/bin/bash\ncat >/dev/null\necho 1\nexit 0\n",
    "docker": (
        "#!/bin/bash\n"
        'case "$*" in\n'
        '  "compose version"|"compose up -d"|info) exit 0 ;;\n'
        '  "compose logs postgres")\n'
        '    printf "PostgreSQL init process complete; ready for start up.\\n"\n'
        '    printf "database system is ready to accept connections\\n"; exit 0 ;;\n'
        "  compose\\ exec*) cat >/dev/null; echo 1; exit 0 ;;\n"
        "  *) exit 1 ;;\n"
        "esac\n"
    ),
}

BOTH_MODELS = (
    '{"models":[{"name":"nomic-embed-text:latest"},{"name":"qwen2.5-coder:7b"}]}'
)


def _workspace(tmp_path: Path) -> Path:
    shim_dir = tmp_path / "bin"
    shim_dir.mkdir(parents=True)
    for name, body in _FAKES.items():
        shim = shim_dir / name
        shim.write_text(body, encoding="utf-8")
        shim.chmod(shim.stat().st_mode | stat.S_IEXEC)
    ws = tmp_path / "workspace"
    ws.mkdir()
    shutil.copy(REPO / "install-core.sh", ws / "install-core.sh")
    shutil.copy(REPO / ".env.example", ws / ".env.example")
    shutil.copy(REPO / "Makefile", ws / "Makefile")
    schema = ws / "src" / "shared" / "_migrations" / "schema.sql"
    schema.parent.mkdir(parents=True)
    schema.write_text("-- schema for the installer test\n", "utf-8")
    return ws


def _run(
    ws: Path, *args: str, tags: str = BOTH_MODELS, setup_rc: int = 0, **env: str
) -> tuple[int, str, list[str]]:
    log = ws.parent / "calls.log"
    proc = subprocess.run(
        ["bash", str(ws / "install-core.sh"), *args],
        capture_output=True,
        text=True,
        env={
            **{k: v for k, v in os.environ.items() if k != "DATABASE_URL"},
            "PATH": os.pathsep.join(
                [str(ws.parent / "bin"), os.environ.get("PATH", "")]
            ),
            "CALL_LOG": str(log),
            "FAKE_TAGS": tags,
            "FAKE_SETUP_RC": str(setup_rc),
            "REAL_PYTHON": sys.executable,
            **env,
        },
        check=False,
        cwd=ws,
    )
    calls = log.read_text("utf-8").splitlines() if log.exists() else []
    return proc.returncode, proc.stdout + proc.stderr, calls


def _setup_calls(calls: list[str]) -> list[str]:
    return [c for c in calls if c.startswith(SETUP)]


def test_ollama_with_both_models_is_set_up_with_the_defaults(tmp_path: Path) -> None:
    ws = _workspace(tmp_path)
    code, out, calls = _run(ws)
    assert code == 0, out
    assert _setup_calls(calls) == [
        f"{SETUP} --url http://localhost:11434 --embedding-model nomic-embed-text "
        "--chat-model qwen2.5-coder:7b"
    ]
    assert "models set up and answering" in out
    assert "ollama pull" not in out
    assert "configure one in .env" not in out


def test_no_model_server_never_fails_the_install(tmp_path: Path) -> None:
    ws = _workspace(tmp_path)
    code, out, calls = _run(ws, tags="DOWN")
    assert code == 0, out
    assert _setup_calls(calls) == []
    assert "no model server found at http://localhost:11434" in out
    assert "https://ollama.com/download" in out
    assert SETUP.removeprefix("run ") in out  # the command to run later


def test_a_missing_model_names_the_pull_command(tmp_path: Path) -> None:
    ws = _workspace(tmp_path)
    tags = '{"models":[{"name":"nomic-embed-text:latest"}]}'
    code, out, _ = _run(ws, tags=tags, setup_rc=1)
    assert code == 0, out
    assert "ollama pull qwen2.5-coder:7b" in out
    assert "ollama pull nomic-embed-text" not in out
    assert "models are not working yet" in out


def test_another_server_with_a_key_skips_detection_and_passes_the_variable(
    tmp_path: Path,
) -> None:
    ws = _workspace(tmp_path)
    code, out, calls = _run(
        ws,
        "--llm-url",
        "https://models.example/v1",
        "--embedding-model",
        "emb-768",
        "--chat-model",
        "chat-1",
        "--llm-api-key-env",
        "MY_KEY",
        tags="DOWN",
        MY_KEY="sk-never-printed",
    )
    assert code == 0, out
    assert _setup_calls(calls) == [
        f"{SETUP} --url https://models.example/v1 --embedding-model emb-768 "
        "--chat-model chat-1 --api-key-env MY_KEY"
    ]
    assert "sk-never-printed" not in out
    assert not any("sk-never-printed" in c for c in calls)


def test_no_llm_skips_model_setup(tmp_path: Path) -> None:
    ws = _workspace(tmp_path)
    code, out, calls = _run(ws, "--no-llm")
    assert code == 0, out
    assert _setup_calls(calls) == []
    assert "skipped (--no-llm)" in out


def test_master_key_is_created_owner_only_and_never_printed(tmp_path: Path) -> None:
    ws = _workspace(tmp_path)
    code, out, _ = _run(ws)
    assert code == 0, out
    secrets = ws / ".secrets" / "core.env"
    line = secrets.read_text("utf-8").strip()
    key = line.removeprefix("CORE_MASTER_KEY=")
    assert line.startswith("CORE_MASTER_KEY=") and len(key) == 44
    from cryptography.fernet import Fernet

    Fernet(key.encode())  # a usable key, not just any base64
    assert stat.S_IMODE(secrets.stat().st_mode) == 0o600
    assert stat.S_IMODE((ws / ".secrets").stat().st_mode) == 0o700
    assert key not in out


def test_an_existing_master_key_is_kept(tmp_path: Path) -> None:
    ws = _workspace(tmp_path)
    (ws / ".secrets").mkdir()
    (ws / ".secrets" / "core.env").write_text("CORE_MASTER_KEY=keep-me\n")
    code, out, _ = _run(ws)
    assert code == 0, out
    assert (ws / ".secrets" / "core.env").read_text() == "CORE_MASTER_KEY=keep-me\n"
    assert "master key present" in out


def test_bare_path_names_the_setup_command_after_start(tmp_path: Path) -> None:
    ws = _workspace(tmp_path)
    code, out, calls = _run(
        ws,
        "--bare",
        "--db-url",
        "postgresql+asyncpg://u:p@db.internal:5432/core",
        "--qdrant-url",
        "http://q.internal:6333",
    )
    assert code == 0, out
    assert _setup_calls(calls) == []  # the API is not running yet in bare mode
    assert "poetry run core-admin llm-resources setup --write" in out
    assert (ws / ".secrets" / "core.env").is_file()


def test_a_separate_embedding_server_is_passed_through(tmp_path: Path) -> None:
    ws = _workspace(tmp_path)
    code, out, calls = _run(
        ws,
        "--llm-url",
        "https://api.anthropic.com/v1",
        "--chat-model",
        "claude",
        "--embedding-url",
        "http://localhost:11434",
        "--llm-api-key-env",
        "MY_KEY",
        MY_KEY="sk-x",
    )
    assert code == 0, out
    assert _setup_calls(calls) == [
        f"{SETUP} --url https://api.anthropic.com/v1 --embedding-model "
        "nomic-embed-text --chat-model claude --embedding-url "
        "http://localhost:11434 --api-key-env MY_KEY"
    ]
