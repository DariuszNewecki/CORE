# Starter Intent — minimal `.intent/` for adopting CORE

This directory is the **source of truth** for the smallest constitution that lets
an external repository be governed by the
[**CORE Constitutional Audit**](https://github.com/DariuszNewecki/CORE).

It is published, as a runnable repository, at
**https://github.com/DariuszNewecki/core-audit-demo** — that repo is a *mirror*
of this directory plus repo scaffolding (LICENSE, its own README). Edit the
starter **here**, in CORE, then run `sync-to-demo.sh` to publish it. Never edit
the mirror directly.

## Why this exists

CORE's own `.intent/` has ~250 files — most of them govern CORE's self-hosting
runtime (workers, flows, proposal lifecycle) and mean nothing to a project that
is merely being audited. Copying all of that into your repo is the wrong move: it
drifts the moment CORE evolves, and it speaks CORE's internal dialect.

This starter is the honest minimum instead. Two layers live here:

| Layer | What it is | Do you edit it? |
|-------|------------|-----------------|
| **Rules** — `constitution/`, `rules/starter.json`, `enforcement/mappings/starter.yaml` | The four universal rules you actually care about, in plain language | **Yes** — this is yours to grow |
| **Machinery** — `META/`, `taxonomies/`, `enforcement/config/` | Schemas, enums, and fail-closed taxonomies the runtime needs to load | **No** — copied verbatim from CORE |

> The machinery is the bulk of the file count and none of the value. A future
> CORE release bundles it into the `core-runtime` wheel, after which your
> `.intent/` shrinks to just the rules layer. The split above is already drawn so
> that change is invisible to adopters.

## What it enforces

See [`.intent/constitution/CONSTITUTION.md`](.intent/constitution/CONSTITUTION.md).
Four deterministic, LLM-free rules: `# ID:` anchors on public symbols (blocking),
docstrings, no `print()` in library code, and no silently-swallowed exceptions.

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
