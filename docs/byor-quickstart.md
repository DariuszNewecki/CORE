# BYOR Quickstart — Govern Your Own Repository

Bring Your Own Rules. This guide takes a completely **fresh machine** — Python
installed, nothing else — through every step needed to place a repo under
constitutional enforcement and verify that the audit catches a real violation.

No CORE source tree. No Postgres. No Qdrant. No LLM required (it helps, but
there is a four-rule fallback menu for offline environments).

---

## What you need

| Requirement | Notes |
|-------------|-------|
| Python ≥ 3.12 | Check: `python3 --version` |
| pip | Usually ships with Python; check: `pip --version` |
| git | The project you want to govern must be a git repository |
| A project with `.py` files | Anything works — a library, a service, even a toy repo |

That is the entire list.

---

## Step 1 — Install the runtime

```bash
pip install core-runtime
```

Verify it landed:

```bash
core-admin --help
```

You should see the top-level command list. If the shell cannot find `core-admin`,
your Python scripts directory is not on `PATH`; add it (e.g.
`~/.local/bin` on Linux, the Scripts folder on Windows) and reload your shell.

---

## Step 2 — Make sure your project is a git repository

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

## Step 3 — Phase A: deliver the machinery floor

The machinery floor is the constitutional infrastructure — META schemas,
taxonomies, a constitution stub, and enforcement configuration. It is bundled
inside the `core-runtime` wheel, so no network call happens here.

```bash
cd /path/to/myproject
core-admin project onboard . --write
```

Expected output ends with something like:

```
🎉 Delivered 29/29 machinery-floor files to /path/to/myproject/.intent/
Next: run `core-admin project scout <target>` to induce and ratify rules …
```

The command is safe to run on any project. It refuses to overwrite an existing
`.intent/` (ADR-111 D3), so there is no accidental clobber risk.

**Preview only (no write)** — omit `--write` to see what would be delivered:

```bash
core-admin project onboard .
```

---

## Step 4 — Phase B: induce and ratify rules

Scout samples your source code, proposes governance rules, and requires you
to ratify each one before writing anything.

```bash
core-admin project scout . --write
```

### With an LLM configured

If `CORE_LLM_URL` or equivalent is set and reachable, Scout calls the LLM with
a structural signal report (line counts, exception patterns, decorator inventory,
…) and proposes rules fitted to your specific codebase. Ratify them one by one:

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

### What gets written

After ratification, two files land in your repo:

```
.intent/rules/scout_inducted.json          ← the ratified rule declarations
.intent/enforcement/mappings/scout.yaml    ← engine + params for each rule
```

**Preview only** — omit `--write` to see what would be written:

```bash
core-admin project scout .
```

---

## Step 5 — Run the audit

```bash
core-admin code audit --offline
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

## Step 6 — Introduce a violation and verify detection

Create a file with a bare `except:` — the blocking rule you ratified in Step 4:

```python
# bad.py
def get_data():
    try:
        return 42
    except:
        pass
```

Run the audit again:

```bash
core-admin code audit --offline
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

## Step 7 — Fix the violation and re-verify

Replace the bare except with a typed handler:

```python
# bad.py (fixed)
def get_data():
    try:
        return 42
    except ValueError:
        return None
```

Run the audit again:

```bash
core-admin code audit --offline
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

**Run Scout again** — as your codebase grows, re-run `project scout . --write`
to surface new patterns. Already-ratified rules are not overwritten; Scout
writes to `scout_inducted.json` (additive unless you edit it).

**Full runtime** — if you want the autonomous daemon (continuous audit →
remediation → commit loop), see [getting-started.md](getting-started.md) for the
Postgres + Qdrant setup.
