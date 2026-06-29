# Cold-reviewer Path

If you want to see CORE govern code in CI without installing anything locally, the shortest path is to add CORE as a GitHub Action and open a pull request.

**One honest prerequisite, stated up front:** the Action audits your repo against the `.intent/` constitution **in that repo** (see below). If your repo doesn't have one yet, scaffold it first — then come back here.

**Govern your own repo (BYOR — Bring Your Own Repository).** Two commands bootstrap a fitted constitution into your repo:

**Step 1 — Deliver the machinery floor** (schemas, taxonomies, enforcement config):

```bash
core-admin project onboard <path-to-your-repo> --write
```

**Step 2 — Induce and ratify rules** (LLM reads your source, proposes candidates, you confirm each):

```bash
core-admin project scout <path-to-your-repo> --write
```

`project scout` requires an LLM resource. Without one it presents a curated menu of four
universal rules for you to accept, reject, or adjust — ratification is always required.
Dry-run (no `--write`) previews what would be written in either command. Once both steps are
done, add the workflow below and open a pull request.

To run the full loop locally on CORE itself in one command, see [Getting Started](getting-started.md) (`./install-core.sh`).

For verifying CORE's claims *about itself* (single gateway, no bypass, no untracked mutation), see the [Proof Index](proof-index.md) instead — that page assumes a running CORE.

---

## What you'll see

CORE reads the `.intent/` directory in your repo, runs the constitutional rules declared there against your `src/` (or whichever paths your rules scope), and posts findings inline on the pull request as GitHub annotations. A failing severity threshold blocks the check; merge protection is yours to configure.

No daemon runs. No database is provisioned. The action is the stateless audit path — Audit tier per ADR-086 D1.

---

## Minimum setup

Your repository needs a `.intent/` directory at the root. If you don't have one, scaffold it with `core-admin project onboard` (see above) before adding the workflow.

Add this workflow at `.github/workflows/core-audit.yml`:

```yaml
name: CORE constitutional audit

on:
  pull_request:
    branches: [main]

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: DariuszNewecki/CORE@main
        with:
          severity: block
```

Open a pull request that touches a file your rules scope. The check runs, annotates findings on the diff if any exist, and exits with `verdict=PASS` or `verdict=FAIL`.

---

## Inputs

| Input | Default | Notes |
|---|---|---|
| `intent-path` | `.intent/` | MVP supports the default only. Custom paths exit with a clear error. |
| `severity` | `block` | One of `block`, `high`, `medium`, `low`, `info`. Findings below this threshold are suppressed. |
| `format` | `github-annotations` | One of `github-annotations`, `json`, `text`. Other formats are useful when piping the action's logs. |

The action emits one output:

- `verdict` — `PASS` (no findings at severity), `FAIL` (findings present), or `ERROR` (internal failure).

---

## Ref stability

The example above pins to `@main` because the audit-engine version bundled in tagged releases lags the latest published `core-runtime` on PyPI; `@main` tracks the most recent pin. Once a release tag lands carrying the current pin, prefer pinning to that tag (e.g. `@v2.7.0`) instead of `@main` for reproducible CI.

---

## Known limits

- `intent-path` other than `.intent/` is rejected; file an issue if you need a non-default path.
- The image is rebuilt on every action invocation (~30s) because no pre-built image is published to a registry. A `docker run` cold path is tracked separately.
- `github-annotations` output renders cleanly only inside GitHub's UI. If you run the action's logic outside CI, override `format` to `text` or `json`.

---

## What this proves

A successful CORE audit on your repo demonstrates three structural claims simultaneously:

1. The rules declared in your `.intent/` were loaded, parsed, and evaluated by named engines (`ast_gate`, `glob_gate`, etc.).
2. Findings, if any, name the rule that produced them — not a generic linter category.
3. The exit code is deterministic from the findings: severity threshold met → fail; no findings → pass; internal failure → error. No silent passes.

This is the same evaluation path the [Proof Index](proof-index.md) claims hold for; this page just lets you observe it without standing up the full runtime.
