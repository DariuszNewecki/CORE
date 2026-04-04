# Getting Started

## Requirements

| Dependency | Version |
|------------|---------|
| Python | ≥ 3.11 |
| PostgreSQL | ≥ 14 |
| Qdrant | latest |
| Docker | for services |
| Poetry | for deps |

You will also need an Anthropic API key. CORE uses Claude as its primary cognitive resource.

---

## Installation

```bash
git clone https://github.com/DariuszNewecki/CORE.git
cd CORE
poetry install

cp .env.example .env
# Add your API keys to .env

make db-setup
```

---

## Your First Audit

Once installed, run a constitutional audit to see the current state of the codebase:

```bash
poetry run core-admin code audit
```

This runs all 92 constitutional rules across 7 enforcement engines and reports:

- **Blocking violations** — must be resolved before autonomous operation
- **Warnings** — tracked but non-blocking
- **Advisory findings** — informational

A clean audit (zero blocking violations) is the precondition for autonomous operation.

---

## Key Commands

Sync the knowledge graph after code changes:

```bash
poetry run core-admin dev sync --write
```

Check infrastructure health:

```bash
poetry run core-admin admin status
```

View governance coverage:

```bash
poetry run core-admin constitution status
```

---

## Understanding the Output

CORE's audit output is structured by policy domain. Each finding references:

- The rule that fired
- The file and line where the violation occurred
- The enforcement engine that detected it
- The enforcement strength (Blocking / Reporting / Advisory)

Blocking violations halt autonomous execution. They must be resolved — either by fixing the violation or by amending the constitution through the governed proposal process.

---

## Next Steps

- [How It Works](how-it-works.md) — understand the constitutional model before making changes
- [CLI Reference](cli-reference.md) — full command reference
- [Contributing](contributing.md) — if you want to engage with the project
