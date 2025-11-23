# Batch Mode

Batch Mode allows you to run CORE operations **non-interactively**, making it ideal for:

* CI pipelines
* automated governance runs
* large-scale validation
* repeated development workflows

Batch Mode never bypasses governance — it simply chains operations safely.

---

# 1. What Batch Mode *Is*

Batch Mode is a way to:

* execute multiple CLI operations in sequence,
* use CORE as a pre-commit/pre-merge gate,
* enforce audits and validations automatically,
* run self-healing or knowledge-sync steps.

It is **not**:

* a background daemon,
* an autonomous long-running process,
* a way to skip human approval.

Everything still runs through controlled CLI flows.

---

# 2. Typical Batch Mode Use Cases

## 2.1. Pre-Commit Hook

Run before every commit:

```bash
poetry run core-admin fix ids --write
poetry run core-admin fix code-style --write
poetry run core-admin manage database sync-knowledge
poetry run core-admin check audit
```

## 2.2. CI/CD Pipeline

A reliable CI sequence:

```yaml
- run: poetry install
- run: poetry run core-admin fix ids --write
- run: poetry run core-admin fix code-style --write
- run: poetry run core-admin manage database sync-knowledge
- run: poetry run core-admin check audit
```

## 2.3. Automated Validation of Large Refactors

Useful when making wide structural changes.

```bash
poetry run core-admin fix all --dry-run
poetry run core-admin fix all --write
poetry run core-admin manage database sync-knowledge
poetry run core-admin check audit
```

## 2.4. Batch Regeneration of Metadata

If you modify many files at once (renames, moves, reorganization):

```bash
poetry run core-admin fix ids --write
poetry run core-admin fix headers --write
poetry run core-admin manage database sync-knowledge
```

---

# 3. Why Batch Mode Matters

CORE enforces governance. Batch Mode ensures that:

* developers cannot accidentally bypass mandatory steps,
* CI systems reproduce the same checks as local environments,
* knowledge remains synchronized,
* autonomous behaviors remain safe.

Batch Mode = **repeatable, governed, deterministic**.

---

# 4. Example: Full Batch Script

A typical script:

```bash
#!/bin/bash
set -e

poetry run core-admin fix ids --write
poetry run core-admin fix code-style --write
poetry run core-admin fix headers --write
poetry run core-admin manage database sync-knowledge
poetry run core-admin check audit
```

* `set -e` aborts on first failure.
* Script can be run locally or in CI.

---

# 5. Safe Batch Mode Patterns

### ✔ Always sync knowledge

Because CORE uses knowledge for:

* audit boundaries
* capability indexing
* drift detection

### ✔ Always audit at the end

This ensures all intermediate actions respect the constitution.

### ✔ Never auto-apply crates

Batch Mode should **not integrate autonomous crates**.
Developers must always review them.

---

# 6. Anti-Patterns (Do Not Do This)

### ❌ Skipping audit

Dangerous — may integrate invalid or unsafe code.

### ❌ Auto-integrating crates

Agents are powerful, but **humans must approve** code.

### ❌ Running batch mode inside `.intent/`

Never modify `.intent/` without proposals.

### ❌ Long-running background processes

CORE is designed for *explicit* steps — not daemons.

---

# 7. Summary

Batch Mode provides:

* repeatability
* determinism
* governance alignment
* tooling standardization

Use it for automation — but always respect CORE’s constitutional workflow.

Next:
`04-secrets-management.md`
