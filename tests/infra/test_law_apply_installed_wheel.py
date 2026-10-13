"""ADR-170 Stage 1 -- ``law apply`` proven from the installed wheel.

``core-law`` runs only released code (ADR-170 D2), so this installs the
wheel from ``dist/`` into a fresh venv (the runtime dependencies from
``poetry.lock``, hash-pinned, binary only, exactly as core-law-setup
installs them) and drives the real
console script against a copy of CORE's law:

- the account restriction: as any account but ``core-law`` it refuses,
  with ``--write`` or without, and writes nothing;
- default read-only: without ``--write`` it shows the report and writes
  nothing;
- explicit ``--write``: it asks for the typed id on a terminal; a wrong id
  writes nothing, the right one writes the bytes and one ledger line whose
  SSH signature verifies; without a terminal it refuses.

Throughout: no ``git`` is run (a trap ``git`` is first on PATH and records
any call), no module is imported from the development tree, and an
unreadable ``.env`` in the repository does not matter.

The two ``--write`` paths run with the wheel's account check answered as
``core-law`` (a one-line stub in the probe): this host has no such account
before Stage 1's root session. The unstubbed refusal is the first test; the
real account is proven by Stage 1 acceptance checks 5-7.

Skipped when no wheel is in ``dist/`` (CI's hermetic job builds one).
"""

from __future__ import annotations

import json
import os
import pty
import select
import shutil
import subprocess
import sys
import time
import tomllib
import venv
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
DIST_DIR = REPO_ROOT / "dist"
PROPOSAL_ID = "0001-wheel-test"
TARGET = ".specs/registers/lessons-register.md"
# The governed file the proposal changes; placed into the scratch copy so the
# test does not depend on any particular .specs/ file in the repository.
TARGET_SOURCE = Path(__file__).resolve().parent / "fixtures" / "lessons-register.md"
COPIED = (".intent", ".specs", "CLAUDE.md")
# Linked like law apply's scratch tree links them; never var/, .git, secrets.
NOT_LINKED = {".git", ".claude", ".venv", "var", ".secrets", "dist", "work", "reports"}

# The account check answered as core-law; everything else is the wheel's code.
# At exit, list any module loaded from outside the venv's site-packages that
# lives under the development tree.
STUB = r"""
import atexit, sys
DEV = sys.argv.pop(1) + "/src/"
def _report():
    bad = sorted({getattr(m, "__file__", "") or "" for m in list(sys.modules.values())
                  if (getattr(m, "__file__", "") or "").startswith(DEV)})
    sys.stderr.write("DEV_IMPORTS=" + repr(bad) + "\n")
atexit.register(_report)
import body.governance.law_custody.writer as writer
writer.current_account = lambda: "core-law"
from cli.admin_cli import app
sys.argv = ["core-admin", *sys.argv[1:]]
app()
"""


def _latest_wheel() -> Path | None:
    # The wheel of this tree's version, never whichever sorts last: "2.11.0"
    # sorts after "2.10.x" and "2.14.x" alike, and predates `law`.
    version = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())["project"][
        "version"
    ]
    wheel = DIST_DIR / f"core_runtime-{version}-py3-none-any.whl"
    return wheel if wheel.is_file() else None


def _requirements(tmp: Path) -> Path:
    import importlib.machinery
    import importlib.util

    # core-law-setup's pinning: the runtime group only, as core-law gets it.
    loader = importlib.machinery.SourceFileLoader(
        "core_law_setup_for_test", str(REPO_ROOT / "infra" / "core-law-setup")
    )
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[loader.name] = module
    loader.exec_module(module)
    path = tmp / "requirements.txt"
    path.write_text(
        module.requirements_from_lock((REPO_ROOT / "poetry.lock").read_bytes())
    )
    return path


@pytest.fixture(scope="module")
def installed(tmp_path_factory: pytest.TempPathFactory) -> Path:
    wheel = _latest_wheel()
    if wheel is None:
        pytest.skip("No wheel for this version in dist/. Run `poetry build` first.")
    tmp = tmp_path_factory.mktemp("law-wheel")
    venv_dir = tmp / "venv"
    venv.create(venv_dir, with_pip=True)
    pip = str(venv_dir / "bin" / "pip")
    for args in (
        ["--only-binary=:all:", "--require-hashes", "-r", str(_requirements(tmp))],
        ["--no-deps", "--no-index", str(wheel)],
    ):
        done = subprocess.run(
            [pip, "install", "--quiet", *args],
            capture_output=True,
            text=True,
            check=False,
        )
        assert done.returncode == 0, done.stderr[-2000:]
    # The venv check core-law-setup applies before it accepts a venv: no .pth
    # file or editable install may point outside it (2026-10-11: the dev group
    # brought two .pth files and the real setup refused).
    setup = sys.modules["core_law_setup_for_test"]
    version = wheel.name.split("-")[1]
    problems = setup.venv_problems(venv_dir, version)
    # This test installs the wheel from a local file, so pip records a
    # direct_url.json and the check rightly calls it "not a release"; the
    # real setup installs from the index. Everything else must be clean.
    assert [p for p in problems if "installed from a path or URL" not in p] == []
    return venv_dir


@pytest.fixture
def world(tmp_path: Path, installed: Path) -> dict[str, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    for name in COPIED:
        source = REPO_ROOT / name
        if source.is_dir():
            shutil.copytree(
                source, repo / name, ignore=shutil.ignore_patterns("__pycache__")
            )
        else:
            shutil.copy2(source, repo / name)
    for entry in REPO_ROOT.iterdir():
        if (
            entry.name not in COPIED
            and entry.name not in NOT_LINKED
            and not entry.name.startswith((".env", ".mypy", ".pytest", ".ruff", ".cov"))
        ):
            (repo / entry.name).symlink_to(entry)
    (repo / TARGET).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(TARGET_SOURCE, repo / TARGET)
    (repo / ".env").write_text("DATABASE_URL=postgresql://nobody@nowhere/none\n")
    (repo / ".env").chmod(0)
    proposal = repo / "var" / "law-proposals" / PROPOSAL_ID
    (proposal / "files" / Path(TARGET).parent).mkdir(parents=True)
    new = (
        repo / TARGET
    ).read_text() + "| L999 | 2026-10-11 | wheel test row | test | open |\n"
    (proposal / "files" / TARGET).write_text(new)
    (proposal / "proposal.md").write_text(
        "# Proposal 0001\n\n## Declared warnings\n\n- a test row\n"
    )
    trap = tmp_path / "trap"
    trap.mkdir()
    (trap / "git").write_text(
        f'#!/bin/sh\necho "$@" >> {tmp_path / "git-calls.log"}\nexit 1\n'
    )
    (trap / "git").chmod(0o755)
    key = tmp_path / "key" / "ledger"
    key.parent.mkdir()
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True
    )
    (tmp_path / "stub.py").write_text(STUB)
    law = tmp_path / "release-law"  # stands in for /opt/core/law
    for name in (".intent", ".specs"):
        shutil.copytree(repo / name, law / name)
    return {
        "law": law,
        "tmp": tmp_path,
        "repo": repo,
        "venv": installed,
        "key": key,
        "trap": trap,
        "new": proposal / "files" / TARGET,
    }


def _env(w: dict[str, Path]) -> dict[str, str]:
    return {
        "PATH": f"{w['trap']}:{w['venv'] / 'bin'}:/usr/bin:/bin",
        "HOME": str(w["tmp"]),
        "LANG": "C.UTF-8",
        "SUDO_USER": "darek",
        # Never the host's durable custody ledger: this test owns its ledgers.
        "CORE_CUSTODY_LEDGER": str(w["tmp"] / "no-custody" / "ledger.jsonl"),
    }


def _args(w: dict[str, Path], *extra: str) -> list[str]:
    return [
        "law",
        "apply",
        PROPOSAL_ID,
        "--key",
        str(w["key"]),
        "--scratch",
        str(w["tmp"] / "scratch"),
        # Never the host's live /opt/core/law: a second destination of our own.
        "--release-law",
        str(w["law"]),
        *extra,
    ]


def _stubbed(w: dict[str, Path]) -> list[str]:
    return [
        str(w["venv"] / "bin" / "python"),
        "-I",
        str(w["tmp"] / "stub.py"),
        str(REPO_ROOT),
    ]


def _assert_untouched(w: dict[str, Path]) -> None:
    assert (w["repo"] / TARGET).read_bytes() == TARGET_SOURCE.read_bytes()
    # The repository's own ledger (law 0024 onward) is copied in; untouched means
    # byte-identical to it, or still absent where the copy has none.
    ledger = w["repo"] / ".intent" / "custody" / "ledger.jsonl"
    original = REPO_ROOT / ".intent" / "custody" / "ledger.jsonl"
    if original.exists():
        assert ledger.read_bytes() == original.read_bytes()
    else:
        assert not ledger.exists()


def _assert_clean_run(w: dict[str, Path], stderr: str) -> None:
    assert not (w["tmp"] / "git-calls.log").exists(), "law apply ran git"
    assert "DEV_IMPORTS=[]" in stderr, stderr[-3000:]


def _run_in_pty(
    command: list[str], cwd: Path, env: dict[str, str], typed: str
) -> tuple[int, str]:
    master, slave = pty.openpty()
    proc = subprocess.Popen(
        command, cwd=cwd, env=env, stdin=slave, stdout=slave, stderr=subprocess.PIPE
    )
    os.close(slave)
    output, sent, deadline = b"", False, time.monotonic() + 600
    while proc.poll() is None and time.monotonic() < deadline:
        ready, _, _ = select.select([master], [], [], 1.0)
        if ready:
            try:
                output += os.read(master, 65536)
            except OSError:
                break
        if not sent and b"Type the proposal id" in output:
            os.write(master, typed.encode() + b"\n")
            sent = True
    proc.wait(timeout=60)
    stderr = proc.stderr.read().decode() if proc.stderr else ""
    os.close(master)
    return proc.returncode, output.decode(errors="replace") + stderr


@pytest.mark.e2e
@pytest.mark.slow
# ID: 18beb3ee-2d98-4826-a7b2-f47466032a9c
def test_refuses_any_account_but_core_law(world: dict[str, Path]) -> None:
    for extra in ((), ("--write",)):
        done = subprocess.run(
            [str(world["venv"] / "bin" / "core-admin"), *_args(world, *extra)],
            cwd=world["repo"],
            env=_env(world),
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        assert done.returncode == 1, done.stdout + done.stderr
        assert "runs only as core-law" in done.stdout
    _assert_untouched(world)
    assert not (world["tmp"] / "git-calls.log").exists()


@pytest.mark.e2e
@pytest.mark.slow
# ID: 4a706f57-b0ae-4ea9-b812-a1c6b6678652
def test_without_write_it_reports_and_writes_nothing(world: dict[str, Path]) -> None:
    done = subprocess.run(
        [*_stubbed(world), *_args(world)],
        cwd=world["repo"],
        env=_env(world),
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    assert done.returncode == 0, done.stdout[-3000:] + done.stderr[-3000:]
    assert "Warnings declared by the proposer" in done.stdout
    assert "a test row" in done.stdout
    assert "law_loads: ok" in done.stdout and "references: 0 dangling" in done.stdout
    assert "Report only; nothing written" in done.stdout
    _assert_untouched(world)
    _assert_clean_run(world, done.stderr)


@pytest.mark.e2e
@pytest.mark.slow
# ID: 54575a05-3d24-46bd-9c4c-cacb52dad768
def test_write_needs_a_terminal_and_the_typed_id(world: dict[str, Path]) -> None:
    command = [*_stubbed(world), *_args(world, "--write")]

    no_tty = subprocess.run(
        command,
        cwd=world["repo"],
        env=_env(world),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    assert no_tty.returncode == 1 and "needs a terminal" in no_tty.stdout
    _assert_untouched(world)

    code, output = _run_in_pty(command, world["repo"], _env(world), "0002-other")
    assert code == 1 and "Not approved; nothing written" in output, output[-3000:]
    _assert_untouched(world)

    code, output = _run_in_pty(command, world["repo"], _env(world), PROPOSAL_ID)
    assert code == 0, output[-3000:]
    _assert_clean_run(world, output)
    assert (world["repo"] / TARGET).read_bytes() == world["new"].read_bytes()
    ledger = (world["repo"] / ".intent" / "custody" / "ledger.jsonl").read_bytes()
    original = REPO_ROOT / ".intent" / "custody" / "ledger.jsonl"
    before = original.read_bytes() if original.exists() else b""
    assert ledger.startswith(before) and ledger[len(before) :].count(b"\n") == 1
    line = json.loads(ledger[len(before) :])
    assert line["proposal"] == PROPOSAL_ID and line["approver"] == "darek"
    assert line["destinations"] == [str(world["repo"]), str(world["law"])]
    assert (world["law"] / TARGET).read_bytes() == world["new"].read_bytes()
    assert (
        (world["law"] / ".intent" / "custody" / "ledger.jsonl")
        .read_bytes()
        .endswith(ledger[len(before) :])
    )
    signature = line.pop("signature")
    (world["tmp"] / "sig").write_text(signature)
    (world["tmp"] / "allowed").write_text(
        'core-law namespaces="core-law-ledger" '
        + world["key"].with_suffix(".pub").read_text()
    )
    verify = subprocess.run(
        [
            "ssh-keygen",
            "-Y",
            "verify",
            "-f",
            str(world["tmp"] / "allowed"),
            "-I",
            "core-law",
            "-n",
            "core-law-ledger",
            "-s",
            str(world["tmp"] / "sig"),
        ],
        input=json.dumps(line, sort_keys=True, separators=(",", ":")).encode(),
        capture_output=True,
        check=False,
    )
    assert verify.returncode == 0, verify.stderr
