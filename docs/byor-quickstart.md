# BYOR Quickstart — Govern Your Own Repository

Bring Your Own Rules. This guide takes a repo through every step needed to
place it under constitutional enforcement and verify that the audit catches a
real violation.

**Two different tools are involved**, and they have different infrastructure
needs:

- `core project onboard`/`promote`/`scout` (Phases A/B below) go through
  `core-cli`, a pure-HTTP client (ADR-146 D2) — they talk to a running
  **CORE API** instance over HTTP. There is currently no offline/zero-infra
  mode for these; the API itself needs Postgres + Qdrant behind it (see
  [getting-started.md](getting-started.md)).
- `core-admin code audit --offline` (Steps 6-8 below) needs **no** running
  services at all — it reads `.intent/` and your source tree directly.

If you already have a CORE instance running somewhere (your own dev install,
or a shared team instance), skip straight to Step 3 and point `CORE_API_URL`
at it. If not, Step 2 below is the fastest path to a local one.

---

## What you need

| Requirement | Notes |
|-------------|-------|
| Python ≥ 3.12 | Check: `python3 --version` |
| pip | Usually ships with Python; check: `pip --version` |
| git | The project you want to govern must be a git repository |
| A project with `.py` files | Anything works — a library, a service, even a toy repo |
| A reachable CORE API | Either one you already run, or the local one you stand up in Step 2 |

**Co-location note:** `onboard`/`promote` write `.intent/` on the **API
host's** filesystem, not the machine running `core-cli` — per ADR-054 D3,
`core-api` is loopback-bound and unauthenticated (single-operator, Phase 1),
so it can't safely accept writes to an arbitrary path from an untrusted
remote client. Run `core-cli` on the same host as the CORE API (or the CORE
API on the same host as your target repo). `scout`'s ratified rule files, by
contrast, are written locally by `core-cli` itself — only the rule
*induction* (reading your code, proposing candidates) goes over the API.
Details: F-1, `.specs/planning/archive/CORE-CLI-2.9.0-Followups.md`.

**Always pass an absolute path** to `onboard`/`promote`/`scout` — never `.`.
`core-cli` sends `path` as a plain string over HTTP; a relative path is
resolved by whichever process receives it (the CORE API for `onboard`/
`promote`), not by your own shell. `.` would silently target the API
server's own working directory instead of your project. Use `$(pwd)` or a
full path instead.

---

## Step 1 — Install the CLI

```bash
pip install core-cli
```

`core-cli` depends on `core-runtime`, so this pulls in both entry points:

```bash
core --help          # consumer CLI — onboard, scout, audit-via-API, etc.
core-admin --help    # operator CLI — offline audit, daemon control, etc.
```

If the shell cannot find either command, your Python scripts directory is not
on `PATH`; add it (e.g. `~/.local/bin` on Linux, the Scripts folder on
Windows) and reload your shell.

---

## Step 2 — Make sure a CORE API is reachable

Skip this if you already have a CORE instance running and reachable.

```bash
git clone https://github.com/DariuszNewecki/CORE.git
cd CORE
poetry install
cp .env.example .env
docker compose up -d                        # Postgres + Qdrant
docker compose exec -T postgres psql -U postgres -d core < schema.sql
```

Start the API server. In a fresh clone with no systemd user units installed
yet, run this in its own terminal (or background it):

```bash
poetry run uvicorn src.api.main:create_app --factory --host 127.0.0.1 --port 8000 --env-file .env
```

(`core-admin daemon up` is the operator shortcut for this once you've
installed CORE's systemd user units — see getting-started.md — but assumes
they already exist; it's not the bootstrap path for a brand-new machine.)

By default `core-cli` talks to `http://127.0.0.1:8000` (trusted-localhost,
no auth). If your CORE API is elsewhere, or on a different port, point at it:

```bash
export CORE_API_URL=http://<core-host>:8000
```

Full setup detail (LLM configuration, manual install path, verifying the
connection): [getting-started.md](getting-started.md).

---

## Step 3 — Make sure your project is a git repository

CORE reads the project root from the nearest `.git/` directory above your
working directory. If your project is not tracked by git yet:

```bash
cd /path/to/myproject
git init
git add .
git commit -m "initial commit"
```

If it already has a `.git/` directory, no action needed.

---

## Step 4 — Phase A: deliver the machinery floor

The machinery floor is the constitutional infrastructure — META schemas,
taxonomies, a constitution stub, and enforcement configuration. It ships
bundled inside the `core-runtime` wheel that the CORE API is running.

```bash
core project onboard /path/to/myproject --write
```

Expected output:

```
Onboarding repository (Phase A — machinery floor): /path/to/myproject
Onboarding complete (write).
```

The command is safe to run on any project. It refuses to overwrite an
existing `.intent/` (ADR-111 D3), so there is no accidental clobber risk.

**Preview only (no write)** — omit `--write` to see what would be delivered:

```bash
core project onboard /path/to/myproject
```

---

## Step 5 — Phase B: induce and ratify rules

Scout samples your source code, proposes governance rules, and requires you
to ratify each one before writing anything.

```bash
core project scout /path/to/myproject --write
```

### With an LLM configured

If the CORE API instance has an LLM provider configured and reachable, Scout
calls it with a structural signal report (line counts, exception patterns,
decorator inventory, …) and proposes rules fitted to your specific codebase.
Ratify them one by one:

```
Rule 1 / N
  OBSERVATION
  ID:          scout.no_bare_except
  Statement:   Code MUST NOT swallow exceptions with a bare 'except:'…
  Enforcement: blocking
  ENFORCEMENT  Engine: regex_gate  …
  a = accept · r = reject · c = change enforcement level
Action [a/r/c] (a):
```

Press **Enter** to accept the default (`a`), or type `r` to reject or `c` to
change the enforcement level before accepting.

### Without an LLM (offline / no key)

Scout falls back to a curated four-rule menu — the same universal rules used
in the proof that shipped the BYOR capability:

| Rule ID | Statement | Default enforcement |
|---------|-----------|---------------------|
| `scout.no_bare_except` | No bare `except:` or `except Exception: pass` | **blocking** |
| `scout.docstrings` | Public functions and classes must have a docstring | reporting |
| `scout.no_print` | No `print()` in importable library code | reporting |
| `scout.no_secrets` | No hardcoded credentials in string literals | reporting |

You still ratify each one — the fallback is a menu, not an auto-accept.

### What gets written, and where

Rule induction (reading your code, proposing candidates) happens on the CORE
API. The ratified result is written **locally**, by `core-cli`, on the
machine you ran `core project scout` from:

```
.intent/rules/scout_inducted.json          ← the ratified rule declarations
.intent/enforcement/mappings/scout.yaml    ← engine + params for each rule
```

**Preview only** — omit `--write` to see what would be written:

```bash
core project scout /path/to/myproject
```

---

## Step 6 — Run the audit

This is the one command in this guide that needs no running services —
it reads `.intent/` and your source tree directly. Pass `--target` (only
valid with `--offline`) since this guide never `cd`s into the project:

```bash
core-admin code audit --offline --target /path/to/myproject
```

On a project with no violations, you will see:

```
╭─ Final Verdict ─╮
│ PASS            │
╰─────────────────╯
```

The `--offline` flag skips engines that require the knowledge graph or an LLM
(`knowledge_gate`, `llm_gate`). For pure BYOR enforcement this is the normal
operating mode.

---

## Step 7 — Introduce a violation and verify detection

Create a file with a bare `except:` — the blocking rule you ratified in
Step 5 — inside `/path/to/myproject`:

```python
# /path/to/myproject/bad.py
def get_data():
    try:
        return 42
    except:
        pass
```

Run the audit again:

```bash
core-admin code audit --offline --target /path/to/myproject
```

Expected output includes:

```
┃ Severity ┃ Count ┃
┡━━━━━━━━━━╇━━━━━━━┩
│ BLOCK    │     2 │

╭─ Final Verdict ─╮
│ FAIL            │
╰─────────────────╯
```

Two BLOCK findings because the regex matches both `except:` and the
`pass` on the following line. Both match the `no_bare_except` rule.

---

## Step 8 — Fix the violation and re-verify

Replace the bare except with a typed handler:

```python
# /path/to/myproject/bad.py (fixed)
def get_data():
    try:
        return 42
    except ValueError:
        return None
```

Run the audit again:

```bash
core-admin code audit --offline --target /path/to/myproject
```

```
╭─ Final Verdict ─╮
│ PASS            │
╰─────────────────╯
```

Your repository is now under constitutional enforcement.

---

## What was just built

```
myproject/
├── .intent/
│   ├── META/                          ← schemas, vocabulary, operational taxonomy
│   ├── constitution/                  ← constitution stub (extend per ADR-111)
│   ├── enforcement/
│   │   ├── config/                    ← action risk, operational mode config
│   │   └── mappings/
│   │       └── scout.yaml             ← your ratified rules → engine mapping
│   ├── rules/
│   │   └── scout_inducted.json        ← your ratified rule declarations
│   └── taxonomies/                    ← operational capabilities, capability tiers
└── bad.py (or your real source files)
```

The `.intent/` directory is the living constitution of your repository.
Commit it — it belongs in version control alongside the code it governs.

---

## Next steps

**Add the GitHub Action** — run the audit on every pull request without a local
install. See [cold-reviewer.md](cold-reviewer.md) for setup (two files, five
minutes).

**Promote rules to blocking** — any `reporting` rule can be changed to
`blocking` by editing `scout_inducted.json` and the enforcement level in
`scout.yaml`. Re-run the audit to confirm the escalation works before committing.

**Add custom rules** — write a rule document in
`.intent/rules/your_rules.json` following the same schema as
`scout_inducted.json`, add an entry to `.intent/enforcement/mappings/your.yaml`,
and the next audit will pick it up automatically.

**Run Scout again** — as your codebase grows, re-run `core project scout
/path/to/myproject --write` to surface new patterns. Already-ratified rules are not overwritten;
Scout writes to `scout_inducted.json` (additive unless you edit it).

**Full runtime** — if you want the autonomous daemon (continuous audit →
remediation → commit loop), see [getting-started.md](getting-started.md) for
the full Postgres + Qdrant setup and `core-admin daemon up`.
