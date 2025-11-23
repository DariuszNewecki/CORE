# CORE CLI Workflows

This guide explains **how to perform common end‑to‑end workflows** using the `core-admin` CLI.

Where the *CLI Reference* lists all commands, this document shows **how they fit together into real development flows** under the Mind–Body–Will architecture.

All workflows reflect the **actual functionality** of the current 2025 CORE codebase.

---

# 1. Add a New Feature (Autonomous Development)

This is the most common workflow: using governed autonomy to create new functionality.

## 🔷 Step 1 — Ask CORE to generate a feature

```bash
poetry run core-admin develop feature "Add health endpoint"
```

This triggers:

* crate creation
* context building
* agent planning & coding
* validation
* constitutional audit

A crate is created under:

```
.core/crates/<id>/
```

## 🔷 Step 2 — Inspect the crate

Review:

* generated code
* generated tests
* validation output
* audit report

Crates are **never** applied automatically.

## 🔷 Step 3 — Manually integrate the changes

Copy changes into `src/`.

## 🔷 Step 4 — Run self-healing tools

```bash
poetry run core-admin fix ids --write
poetry run core-admin fix code-style --write
```

## 🔷 Step 5 — Update CORE's knowledge

```bash
poetry run core-admin manage database sync-knowledge
```

## 🔷 Step 6 — Run the constitutional audit

```bash
poetry run core-admin check audit
```

Only when audit passes, commit and push.

---

# 2. Refactor Existing Code (Manual Developer Flow)

This workflow is **100% manual** (A1 autonomy does not refactor code by itself).

## 🔷 Step 1 — Make changes normally

Modify code under `src/`.

## 🔷 Step 2 — Fix metadata

```bash
poetry run core-admin fix ids --write
poetry run core-admin fix headers --write
```

## 🔷 Step 3 — Run style & linting

```bash
poetry run core-admin fix code-style --write
```

## 🔷 Step 4 — Sync knowledge

```bash
poetry run core-admin manage database sync-knowledge
```

## 🔷 Step 5 — Audit

```bash
poetry run core-admin check audit
```

Commit only when clean.

---

# 3. Fix Audit Violations

This workflow applies when the Constitutional Auditor rejects a change.

## 🔷 Step 1 — Run audit

```bash
poetry run core-admin check audit
```

## 🔷 Step 2 — Read findings

Violations include:

* domain placement
* import rules
* security checks
* ID/capability hygiene
* missing headers
* drift
* schema issues

## 🔷 Step 3 — Apply targeted remediations

Some examples:

```bash
poetry run core-admin fix ids --write
poetry run core-admin fix headers --write
poetry run core-admin fix docstrings --write
```

## 🔷 Step 4 — Re‑audit

```bash
poetry run core-admin check audit
```

Repeat until clean.

---

# 4. Sync Knowledge Graph After Structural Changes

CORE uses a Knowledge Graph to understand:

* symbols
* capabilities
* linkages
* boundaries
* drift

Whenever adding or removing modules, functions, or capabilities:

## 🔷 Step 1 — Make changes

## 🔷 Step 2 — Fix IDs

```bash
poetry run core-admin fix ids --write
```

## 🔷 Step 3 — Sync knowledge

```bash
poetry run core-admin manage database sync-knowledge
```

## 🔷 Step 4 — Audit

```bash
poetry run core-admin check audit
```

---

# 5. Update or Add Documentation Metadata

Documentation improvements are also governed.

## 🔷 Step 1 — Edit files normally

## 🔷 Step 2 — Fix headers (ensures file path metadata)

```bash
poetry run core-admin fix headers --write
```

## 🔷 Step 3 — Audit

```bash
poetry run core-admin check audit
```

---

# 6. Submit a Constitutional Proposal (for `.intent/` changes)

Only use this workflow when changing:

* policies
* schemas
* governance domains
* capability taxonomy
* constitutional rules

## 🔷 Step 1 — Create a proposal

```bash
poetry run core-admin manage proposals new "Reason for change"
```

## 🔷 Step 2 — Sign it

```bash
poetry run core-admin keys keygen "your.email@example.com"
```

## 🔷 Step 3 — Canary audit (automatic)

CORE applies the proposal to a temporary clone and audits it.

## 🔷 Step 4 — Submit to approvers

Depending on your governance model.

---

# 7. Investigate Structural Problems

If something seems off (drift, missing capabilities, inconsistent imports):

## 🔷 Step 1 — Inspect project

```bash
poetry run core-admin inspect project
```

## 🔷 Step 2 — Search capabilities or symbols

```bash
poetry run core-admin search capability "vector"
poetry run core-admin search symbol "builder"
```

## 🔷 Step 3 — Use self-healing tools

```bash
poetry run core-admin fix all --dry-run
```

## 🔷 Step 4 — Sync knowledge & re-audit

```bash
poetry run core-admin manage database sync-knowledge
poetry run core-admin check audit
```

---

# 8. Full End‑to‑End Example

This is the canonical CORE workflow for contributors.

```bash
# 1. Make changes or generate a crate
poetry run core-admin develop feature "Add capability docs"

# 2. Review crate manually
ls .core/crates/

# 3. Integrate accepted crate
cp -r .core/crates/<id>/changes/* src/

# 4. Self-heal
poetry run core-admin fix ids --write
poetry run core-admin fix code-style --write

# 5. Sync knowledge
a:poetry run core-admin manage database sync-knowledge

# 6. Run audit
poetry run core-admin check audit

# 7. Commit & push
```

---

# 9. Mental Model

CORE workflows always follow the same pattern:

```
Write → Self‑Heal → Sync Knowledge → Audit → Commit
```

For autonomous workflows:

```
Intent → Crate → Validate → Audit → Integrate → Commit
```

These cycles enforce CORE’s **governed evolution** and prevent drift.

---

# 10. When In Doubt

Run:

```bash
poetry run core-admin inspect command-tree
```

Or:

```bash
poetry run core-admin check audit
```

These two commands give you immediate clarity about the system’s state.
