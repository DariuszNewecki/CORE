"""Which trees does this Bash command commit in? Used by the commit hook.

The Claude Code PreToolUse hook core-verdict.sh pipes its payload here:
``python3 -I core-commit-target.py <repo>``.

Output, one line per tree a `git commit` in the command lands in (deduplicated,
in order); no output when the command commits nothing. Exit 2 with a message
on stderr when the payload is not the JSON Claude Code sends; the hook then
refuses rather than passes.

Detection works on the shell words, not a pattern over the text:
- the command is split into simple commands at `;`, `&&`, `||`, `|`, `&`,
  `(`, `)` and newlines; here-document bodies are dropped first;
- leading `NAME=value` assignments and the wrappers `env`, `command`, `exec`,
  `nohup`, `time`, `builtin` are skipped;
- git is matched by basename (`git`, `/usr/bin/git`);
- git's global options are skipped, with the separate argument of those that
  take one (`-C <dir>`, `-c <k=v>`, `--git-dir <d>`, ...); the first other word
  is the subcommand, and `commit` is a commit.
If the words cannot be split (unbalanced quotes), any `git ... commit` in the
raw text counts as a commit in the payload's cwd: refuse rather than miss one.

Out of scope: commands built by hand-quoting, such as `bash -c "git commit"`,
`eval`, `xargs git commit`, aliases and shell functions. The words reach git
only after another round of parsing this file does not do.

The tree of each commit: the payload's cwd, then every `cd`/`pushd` before it
in the command, then the commit's own `-C` options. It counts only when it is
inside this repository or one of its worktrees (same git-common-dir); then its
top level is printed. A commit in another repository prints that repository's
top level when it is governed by CORE (it has a .intent/), so it is judged by
its own law; a repository without .intent/ is not judged and prints nothing.
It used to print the development checkout, which judged a commit elsewhere
against CORE's own, unrelated tree.

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


_SEPARATORS = {";", ";;", "&", "&&", "|", "||", "|&", "(", ")", "\n"}
_WRAPPERS = {"env", "command", "exec", "nohup", "time", "builtin"}
_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
# git global options whose argument is the next word (git(1), "OPTIONS").
_GIT_ARG_OPTIONS = {
    "-C",
    "-c",
    "--git-dir",
    "--work-tree",
    "--namespace",
    "--super-prefix",
    "--config-env",
    "--exec-path",
    "--attr-source",
}
_HEREDOC = re.compile(r"(?<!<)<<(?!<)-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
_LOOSE_COMMIT = re.compile(r"(^|[^A-Za-z0-9_.-])git(\s.*)?\scommit(\s|$)", re.S)
_SAFE = ["-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false"]


def _drop_heredoc_bodies(command: str) -> str:
    """Remove here-document bodies; their lines are data, not commands."""
    out: list[str] = []
    pending: list[str] = []
    for line in command.split("\n"):
        if pending:
            if line.strip() == pending[0]:
                pending.pop(0)
            continue
        out.append(line)
        pending.extend(m.group(2) for m in _HEREDOC.finditer(line))
    return "\n".join(out)


def _simple_commands(command: str) -> list[list[str]]:
    lexer = shlex.shlex(
        _drop_heredoc_bodies(command).replace("\n", " ; "),
        posix=True,
        punctuation_chars=True,
    )
    lexer.whitespace_split = True
    commands: list[list[str]] = [[]]
    for token in lexer:
        if token in _SEPARATORS:
            commands.append([])
        else:
            commands[-1].append(token)
    return [c for c in commands if c]


def _strip_prefix(words: list[str]) -> list[str]:
    i = 0
    while i < len(words):
        word = words[i]
        if _ASSIGNMENT.match(word):
            i += 1
        elif word in _WRAPPERS:
            i += 1
            while i < len(words) and words[i].startswith("-"):
                i += 1
        else:
            break
    return words[i:]


def _git_commit_dirs(words: list[str]) -> list[str] | None:
    """The `-C` directories of a `git ... commit`, or None if not a commit."""
    if not words or os.path.basename(words[0]) != "git":
        return None
    dirs: list[str] = []
    i = 1
    while i < len(words) and words[i].startswith("-"):
        option = words[i]
        if option in _GIT_ARG_OPTIONS:
            if option == "-C" and i + 1 < len(words):
                dirs.append(words[i + 1])
            i += 2
        else:
            i += 1
    if i < len(words) and words[i] == "commit":
        return dirs
    return None


def _join(base: str, path: str) -> str:
    return os.path.join(base, os.path.expanduser(path))


def _commit_dirs(command: str, cwd: str) -> list[str]:
    try:
        commands = _simple_commands(command)
    except ValueError:
        return [cwd] if _LOOSE_COMMIT.search(command) else []
    found: list[str] = []
    here = cwd
    for raw in commands:
        words = _strip_prefix(raw)
        if words and words[0] in ("cd", "pushd"):
            args = [w for w in words[1:] if not w.startswith("-")]
            here = _join(here, args[0]) if args else os.path.expanduser("~")
            continue
        dirs = _git_commit_dirs(words)
        if dirs is not None:
            target = here
            for d in dirs:
                target = _join(target, d)
            found.append(os.path.normpath(target))
    return found


def _git(tree: str, *args: str) -> str:
    if not os.path.isdir(tree):
        return ""
    result = subprocess.run(
        ["git", "-C", tree, *_SAFE, *args],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _tree(target: str, repo: str, repo_common: str) -> str:
    common = _git(target, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if common and common == repo_common:
        return _git(target, "rev-parse", "--show-toplevel") or repo
    top = _git(target, "rev-parse", "--show-toplevel")
    if top and os.path.isdir(os.path.join(top, ".intent")):
        return top
    return ""


def main() -> int:
    repo = sys.argv[1]
    try:
        payload = json.load(sys.stdin)
        command = payload["tool_input"]["command"]
        cwd = payload.get("cwd") or repo
        if not isinstance(command, str) or not isinstance(cwd, str):
            raise TypeError("command and cwd must be strings")
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        print(f"unreadable hook payload ({type(exc).__name__}: {exc})", file=sys.stderr)
        return 2
    repo_common = _git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
    trees: list[str] = []
    for target in _commit_dirs(command, cwd):
        tree = _tree(target, repo, repo_common)
        if tree and tree not in trees:
            trees.append(tree)
    print("\n".join(trees))
    return 0


if __name__ == "__main__":
    sys.exit(main())
