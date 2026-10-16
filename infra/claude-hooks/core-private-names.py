"""No private library name leaves this host: the assistant's gate for it.

Claude Code PreToolUse hook (matcher: Bash), installed beside core-verdict.sh.
A repository that governs a private library declares a rule
(process-governance-tool: privacy.no_private_library_names) and ships its
enforcer, scripts/private_names.py. This hook runs that enforcer, as merged
on the repository's origin/main (a branch cannot weaken it), before:

- a `git commit` that lands in that repository (core-commit-target.py
  decides where a commit lands): the command (with its message), the changed
  and untracked paths, the diff against HEAD and the untracked files;
- a `gh issue|pr create|comment|edit|review` or a writing `gh api` call aimed
  at that repository (it is named in the command, or the command runs inside
  its checkout and names no other repository): the command and every file it
  passes as a body (`--body-file F`, `-F key=@F`, `--input F`).

A hit refuses the command (exit 2); the message says where, never the name.
So does anything the hook cannot check: a body read from stdin, an
unreadable body file, a missing enforcer or an enforcer that fails.

Configuration, KEY=VALUE, one repository per file, in
/opt/core/law/private-names/private-names.conf (CORE_PRIVATE_NAMES_CONF in
tests): GITHUB_REPO (owner/name), CHECKOUT (a local clone), LIBRARY (the
private library) and optionally NAMES (people named only inside documents).
It is core-law's (core-law-setup seeds it), so the assistant can read it but
not change, rename or delete it. On a CORE host (a live /opt/core/current) a
missing file blocks every commit and gh write: deleting the configuration
must not switch the check off (governor 2026-10-16). Elsewhere the hook
passes everything.

Scope, honestly: like core-verdict.sh this governs the assistant's commands
only; commands built by hand-quoting (bash -c, eval, xargs) are out of scope.

The installed copy lives in .claude/hooks/ (core-law, not in git); this file
in infra/claude-hooks/ is its source and what CI tests.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path


_HERE = Path(__file__).resolve().parent
_GH_WRITE = re.compile(
    r"\bgh\s+(?:issue|pr)\s+(?:create|comment|edit|review|close|reopen|merge)\b"
)
_GH_API = re.compile(r"\bgh\s+api\b")
# gh api writes with an explicit method, or with fields (gh then POSTs).
_API_WRITES = re.compile(
    r"(?:-X|--method)[\s=]*(?:POST|PATCH|PUT)\b|\s-[fF]\s|--raw-field|--field|--input"
)
# gh options whose value is a file the body is read from, and gh api fields
# whose `key=@file` value is.
_FILE_OPTIONS = {"--body-file", "--input"}
_FIELD_OPTIONS = {"-F", "--field"}
_MAX_UNTRACKED = 1_000_000
# Owned by core-law (core-law-setup seeds it): the assistant reads it and
# cannot change, rename or delete it.
DEFAULT_CONF = "/opt/core/law/private-names/private-names.conf"


def _refuse(message: str) -> int:
    print(f"CORE private names: refused — {message}", file=sys.stderr)
    return 2


def _conf() -> dict[str, str] | None:
    path = Path(os.environ.get("CORE_PRIVATE_NAMES_CONF") or DEFAULT_CONF)
    if not path.is_file():
        return None
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            out[key.strip()] = os.path.expanduser(value.strip())
    return out


def _core_host() -> bool:
    """A host CORE is deployed on (it has a live release)."""
    return Path(os.environ.get("CORE_ROOT", "/opt/core"), "current").exists()


def _git(tree: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", tree, *args], capture_output=True, text=True)


def _common_dir(tree: str) -> str:
    result = _git(tree, "rev-parse", "--path-format=absolute", "--git-common-dir")
    return os.path.realpath(result.stdout.strip()) if result.returncode == 0 else ""


def _commit_trees(payload: str, repo: str) -> list[str]:
    result = subprocess.run(
        [sys.executable, "-I", str(_HERE / "core-commit-target.py"), repo],
        input=payload,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "core-commit-target.py failed")
    return [line for line in result.stdout.splitlines() if line]


def _commit_text(tree: str) -> str:
    parts = [
        _git(tree, "status", "--porcelain", "--untracked-files=all").stdout,
        _git(tree, "diff", "HEAD").stdout,
    ]
    untracked = _git(tree, "ls-files", "--others", "--exclude-standard").stdout.split(
        "\n"
    )
    for rel in filter(None, untracked):
        path = Path(tree) / rel
        if path.is_file() and path.stat().st_size <= _MAX_UNTRACKED:
            parts.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(parts)


def _aims_at(command: str, cwd: str, conf: dict[str, str]) -> bool:
    repo = conf["GITHUB_REPO"]
    if repo in command or repo.split("/")[-1] in command:
        return True
    names_other = re.search(r"(?:\s-R|--repo)[\s=]|repos/", command)
    return not names_other and _common_dir(cwd) == _common_dir(conf["CHECKOUT"])


def _body_files(command: str, cwd: str) -> list[Path]:
    """The files a gh command reads its body from; '-' (stdin) raises."""
    try:
        words = shlex.split(command, posix=True)
    except ValueError:
        words = command.split()
    out = []
    for i, word in enumerate(words):
        following = words[i + 1] if i + 1 < len(words) else ""
        if word in _FILE_OPTIONS:
            value = following
        elif word.split("=", 1)[0] in _FILE_OPTIONS and "=" in word:
            value = word.split("=", 1)[1]
        elif word in _FIELD_OPTIONS and "=@" in following:
            value = following.split("=@", 1)[1]
        else:
            continue
        if value == "-":
            raise ValueError(
                "a body read from stdin cannot be checked; write it to a file"
            )
        out.append(Path(cwd, os.path.expanduser(value)))
    return out


def _check(conf: dict[str, str], text: str, where: str, scratch: str) -> int:
    script = _git(conf["CHECKOUT"], "show", "origin/main:scripts/private_names.py")
    if script.returncode != 0:
        return _refuse(
            f"no enforcer at {conf['CHECKOUT']} origin/main:scripts/private_names.py (git fetch it)"
        )
    with tempfile.TemporaryDirectory(dir=scratch) as tmp:
        enforcer = Path(tmp, "private_names.py")
        enforcer.write_text(script.stdout, encoding="utf-8")
        checked = Path(tmp, "text-to-publish.txt")
        checked.write_text(text, encoding="utf-8")
        env = {**os.environ, "PROCGOV_PRIVATE_LIBRARY": conf["LIBRARY"]}
        if conf.get("NAMES"):
            env["PROCGOV_PRIVATE_NAMES"] = conf["NAMES"]
        python = os.environ.get(
            "CORE_PRIVATE_NAMES_PYTHON", "/opt/core/current/venv/bin/python"
        )
        result = subprocess.run(
            [python, "-I", str(enforcer), str(checked)],
            env=env,
            capture_output=True,
            text=True,
        )
    if result.returncode == 1:
        return _refuse(
            f"{where} holds a name from the private library; describe it plainly"
        )
    if result.returncode != 0 or "nothing to check" in result.stdout:
        detail = (result.stderr or result.stdout).strip()[-300:]
        return _refuse(f"the private-names check could not run ({detail})")
    return 0


def main() -> int:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
        command = payload["tool_input"]["command"]
        cwd = payload.get("cwd") or os.getcwd()
    except (ValueError, KeyError, TypeError) as exc:
        return _refuse(f"unreadable hook payload ({type(exc).__name__})")
    repo = os.environ.get("CLAUDE_PROJECT_DIR", "/opt/dev/CORE")
    try:
        trees = _commit_trees(raw, repo)
    except RuntimeError as exc:
        return _refuse(f"could not tell where the command commits ({exc})")
    gh_write = bool(
        _GH_WRITE.search(command)
        or (_GH_API.search(command) and _API_WRITES.search(command))
    )
    if not trees and not gh_write:
        return 0

    conf = _conf()
    if conf is None:
        if _core_host():
            where = os.environ.get("CORE_PRIVATE_NAMES_CONF") or DEFAULT_CONF
            return _refuse(
                f"no {where}; core-law-setup installs it (governor 2026-10-16)"
            )
        return 0
    missing = [k for k in ("GITHUB_REPO", "CHECKOUT", "LIBRARY") if not conf.get(k)]
    if missing:
        return _refuse(f"private-names.conf lacks {', '.join(missing)}")
    scratch = Path(repo, "var", "tmp")
    scratch.mkdir(parents=True, exist_ok=True)
    target = _common_dir(conf["CHECKOUT"])

    for tree in trees:
        if target and _common_dir(tree) == target:
            status = _check(
                conf, command + "\n" + _commit_text(tree), "this commit", str(scratch)
            )
            if status:
                return status

    if gh_write and _aims_at(command, cwd, conf):
        try:
            files = _body_files(command, cwd)
            bodies = [f.read_text(encoding="utf-8") for f in files]
        except (OSError, ValueError) as exc:
            return _refuse(str(exc))
        return _check(conf, "\n".join([command, *bodies]), "this gh text", str(scratch))
    return 0


if __name__ == "__main__":
    sys.exit(main())
