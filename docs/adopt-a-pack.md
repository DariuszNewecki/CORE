# Add a Rule Pack

A rule pack is a ready-made set of rules with their enforcement mappings. Adopting one
copies it into your repository's `.intent/`, where it becomes your law: you can read it,
change it, or remove it like any rule you wrote yourself.

**You need:** Python 3.12+, `core-runtime` 2.11.0 or later, and a repository that
already carries a `.intent/` machinery floor — one made by
[`core-admin project new`](start-a-project.md) or delivered by
[`core project onboard`](byor-quickstart.md). No services are needed.

## Adopt a pack

Run inside the repository:

```bash
core-admin project adopt-pack core/starter-python             # preview: lists the files it would write
core-admin project adopt-pack core/starter-python --write     # write it
core-admin code audit --offline                               # enforce it
```

`adopt-pack` refuses a directory without the machinery floor: rules without it could
not be evaluated, so the refusal is better than a silent no-op.

## The packs that ship with CORE

| Pack | For | Rules |
|---|---|---|
| `core/starter-python` | Any Python project; the first pack to adopt | 4: `starter.no_bare_except` (blocking), docstrings, no `print()`, no hardcoded secrets (reporting) |
| `core/python-hygiene` | Teams that have outgrown the starter | 8: the starter's four, plus no broad `except`, no f-strings in logger calls (reporting), no hardcoded OS paths, explicit exception logging (advisory) |
| `core/architectural-boundaries` | Layered projects (FastAPI, Django, routes/services/models) | 4, all reporting: no `print()` in services, no raw SQL or direct database access in routes, service docstrings |

`core/python-hygiene` contains the starter's four rules, so adopt one or the other.
`adopt-pack` refuses a pack that declares a rule ID the repository already has — from
another pack or from your own rules — and names each conflict; two declarations of one
rule would stop the audit. To move from the starter to `core/python-hygiene`, delete
`.intent/rules/packs/core_starter_python.json` and
`.intent/enforcement/mappings/packs/core_starter_python.yaml`, then adopt it.

## Enforcement levels

Each rule declares how hard it bites:

- **blocking** — a finding fails the audit (exit code 1) and, in CI, the pull request;
- **reporting** — listed in the audit, does not fail it;
- **advisory** — informational.

To make a rule stricter or looser, change its `enforcement` field in
`.intent/rules/packs/`. The change is yours to review like any other change to your law.

## Where next

- Enforce the same rules on every pull request: [Audit in CI](cold-reviewer.md).
- Write rules fitted to your own code: [Govern your own repository](byor-quickstart.md)
  (`core project scout`).
