# Cold-reviewer Path

If you have not used CORE before and want to see it govern real code — yours — without installing anything locally, the shortest path is to add CORE as a GitHub Action and open a pull request.

This page documents that path. It is not "one command on your laptop." A true one-command demo is filed and tracked, but the honest state today is that the cold-reviewer surface CORE actually ships is the audit action.

For verifying CORE's claims *about itself* (single gateway, no bypass, no untracked mutation), see the [Proof Index](proof-index.md) instead — that page assumes a running CORE.

---

## What you'll see

CORE reads the `.intent/` directory in your repo, runs the constitutional rules declared there against your `src/` (or whichever paths your rules scope), and posts findings inline on the pull request as GitHub annotations. A failing severity threshold blocks the check; merge protection is yours to configure.

No daemon runs. No database is provisioned. The action is the stateless audit path — Audit tier per ADR-086 D1.

---

## Minimum setup

Your repository needs a `.intent/` directory at the root. If you don't have one, the action will fail with a clear error pointing you here.

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
