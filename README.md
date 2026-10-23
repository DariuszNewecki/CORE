# CORE

> **Executable constitutional governance for AI-assisted software development.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/DariuszNewecki/CORE/blob/main/LICENSE)
[![Release](https://img.shields.io/badge/Release-v2.16.0-blue)](https://github.com/DariuszNewecki/CORE/releases)
[![Docs](https://img.shields.io/badge/Docs-online-green)](https://dariusznewecki.github.io/CORE/)

**Current Release:** v2.16.0 — see [CHANGELOG.md](https://github.com/DariuszNewecki/CORE/blob/main/CHANGELOG.md).

## What CORE is

CORE audits a codebase against declared rules in `.intent/`, records every
violation, proposes fixes, and logs the chain from finding to commit. AI
assistants and CORE's own loop can propose changes; only the human governor
approves them. What it is for, in plain words: [What CORE does](https://dariusznewecki.github.io/CORE/what-core-does/).

The `pip install` below gives you the offline audit, CORE's audit on every pull
request (GitHub Action) and, for your AI assistant, the rules and a verdict on
its change before it commits. Recording findings, proposing fixes, CORE's own
loop and changes submitted for your approval need the full local runtime (last
block of this section).

## Install and first run

You need Python 3.12 or later and git. On Debian and Ubuntu, `python3 -m venv`
also needs the `python3-venv` package (`sudo apt install python3-venv git`).

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install core-runtime
```

Current Ubuntu and Debian refuse a bare `pip install` outside a virtual
environment ("externally-managed-environment"); the first line creates one
(`pipx install core-runtime` works too). This gives you the `core-admin` CLI. In a repository that already has a
`.intent/` constitution, audit it with no services running:

```bash
core-admin code audit --offline
```

To bring CORE into an existing repository, no services are needed either:

```bash
cd your-repo
core-admin project init . --write --yes
core-admin project adopt-pack core/starter-python --write
git add .intent .github && git commit -m "Adopt CORE"
core-admin code audit --offline
```

`project init --write` asks for confirmation at a terminal; `--yes` skips the
question, and without a terminal (CI, scripts, AI agents) it stops at once
unless `--yes` is given.

The audit judges the law committed at `HEAD`, so commit `.intent/` first;
uncommitted law reads DEGRADED, never PASS. `project init` also writes CORE's
GitHub Action (`.github/workflows/core-audit.yml`); commit it with the law. The
audit lists blocking and high findings; reporting and advisory ones are only
counted. Add `--severity info` to list them too.

Connect your AI assistant (Claude Code shown; any MCP client works) so it asks
CORE about your project's rules and checks its change before committing; see
[Connect your AI assistant](https://dariusznewecki.github.io/CORE/connect-an-assistant/):

```bash
claude mcp add --scope project core -- core-admin mcp run
```

Claude Code starts `core-admin` itself, so it must be on `PATH` in the shell
you start `claude` from: activate the virtual environment first, or install
with `pipx install core-runtime` (then `pipx ensurepath`) so it is on `PATH` in
every shell. Everyone who uses the committed `.mcp.json` needs the same.

A new project:

```bash
core-admin project new myproject --write
cd myproject
git init
core-admin project adopt-pack core/starter-python --write
git add -A && git commit -m "Adopt core/starter-python"
core-admin code audit --offline
```

To run the full local runtime (Postgres + Qdrant) from a clone (it also needs
Docker with Compose v2 and Poetry; every prerequisite is in
[Run the full runtime](https://dariusznewecki.github.io/CORE/getting-started/)):

```bash
git clone https://github.com/DariuszNewecki/CORE.git
cd CORE
./install-core.sh
```

## More

- Decisions: [.specs/DECISIONS.md](https://github.com/DariuszNewecki/CORE/blob/main/.specs/DECISIONS.md)
- Documentation: [docs/](https://github.com/DariuszNewecki/CORE/blob/main/docs/index.md), published at [dariusznewecki.github.io/CORE](https://dariusznewecki.github.io/CORE/)

## License

MIT — see [LICENSE](https://github.com/DariuszNewecki/CORE/blob/main/LICENSE).
