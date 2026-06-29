# Starter Intent — minimal `.intent/` for adopting CORE

This directory is an **illustrative example** of a minimal constitution in CORE's
enforcement vocabulary, and the **LLM-unavailable fallback** for
[`project scout`](https://github.com/DariuszNewecki/CORE) — CORE's Path 1
(Scout) induction command.

It is published, as a runnable repository, at
**https://github.com/DariuszNewecki/core-audit-demo** — that repo is a *mirror*
of this directory plus repo scaffolding (LICENSE, its own README). Edit the
starter **here**, in CORE, then run `sync-to-demo.sh` to publish it. Never edit
the mirror directly.

## How this fits into the BYOR on-ramp

CORE's onboarding is two steps:

1. **`project onboard <path> --write`** — delivers the machinery floor into your
   repo (`META/`, `taxonomies/`, and `enforcement/config/`) from the bundled
   `core-runtime` wheel. No rules, no LLM.
2. **`project scout <path> --write`** — reads your source code, proposes candidate
   rules that fit your codebase via LLM analysis, and requires you to ratify each
   before delivery. If no LLM is available, it presents the four rules from this
   directory as a curated menu — you still ratify each one.

This directory serves two roles in that model:

| Role | What it means |
|------|---------------|
| **Illustrative** | Shows what a minimal, four-rule constitution looks like in CORE's vocabulary — good onboarding reading |
| **Scout LLM-fallback** | The four rules here are the curated menu `project scout` presents when no LLM is available |

> The machinery layer (`META/`, `taxonomies/`, `enforcement/config/`) is bundled
> in the `core-runtime` wheel (`shared._machinery_floor` package data, ADR-108 D3).
> `project onboard` reads the floor from the installed package — this directory
> serves only as the Scout LLM-fallback rules source, not as the machinery floor source.

## What the four rules enforce

See [`.intent/constitution/CONSTITUTION.md`](.intent/constitution/CONSTITUTION.md).
Four deterministic, LLM-free rules: `# ID:` anchors on public symbols (blocking),
docstrings, no `print()` in library code, and no silently-swallowed exceptions.
These are illustrative universal rules — `project scout` may propose different or
additional rules fitted to your specific codebase.

## Try it locally

```bash
pip install core-runtime
cd examples/starter-intent
core-admin code audit --offline --format=text --severity=block
```

The bundled `src/hello.py` violates all four rules on purpose, so the audit exits
non-zero (one blocking finding). Clean the file up and it goes green. The
`verify.sh` script next to this README runs exactly that check as a regression
guard inside CORE's own CI.
