# CORE

> **Executable constitutional governance for AI-assisted software development.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Release](https://img.shields.io/badge/Release-v2.14.2-blue)](https://github.com/DariuszNewecki/CORE/releases)
[![Docs](https://img.shields.io/badge/Docs-online-green)](https://dariusznewecki.github.io/CORE/)

**Current Release:** v2.14.2 — see [CHANGELOG.md](CHANGELOG.md).

## What CORE is

CORE audits a codebase against declared rules in `.intent/`, records every
violation, proposes fixes, and logs the chain from finding to commit. AI
assistants and CORE's own loop can propose changes; only the human governor
approves them. What it is for, in plain words: [What CORE does](docs/what-core-does.md).

## Install and first run

```bash
pip install core-runtime
```

This gives you the `core-admin` CLI. In a repository that already has a
`.intent/` constitution, audit it with no services running:

```bash
core-admin code audit --offline
```

To bring CORE into an existing repository, onboard it (this uses the `core`
CLI from `pip install core-cli` and a running CORE API):

```bash
core project onboard
```

A new project needs no services at all:

```bash
core-admin project new myproject --write
cd myproject
core-admin project adopt-pack core/starter-python --write
core-admin code audit --offline
```

To run the full local runtime (Postgres + Qdrant) from a clone:

```bash
git clone https://github.com/DariuszNewecki/CORE.git
cd CORE
./install-core.sh
```

## More

- Decisions: [.specs/DECISIONS.md](.specs/DECISIONS.md)
- Documentation: [docs/](docs/index.md), published at [dariusznewecki.github.io/CORE](https://dariusznewecki.github.io/CORE/)

## License

MIT — see [LICENSE](LICENSE).
