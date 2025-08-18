# Contributing to CORE

> **First principle:** The constitution lives in `.intent/`. Touch **.intent first, code second**.

Thanks for helping improve CORE! This guide explains how to propose changes safely and predictably.

---

## 1) Prereqs

* Python **3.9+** (3.11 recommended)
* [Poetry](https://python-poetry.org/) installed
* Install deps: `poetry install`

---

## 2) Branch & Commit Rules

**Branch names**

* `feat/<short-purpose>` — new features
* `fix/<short-purpose>` — bug fixes
* `chore/<short-purpose>` — non-functional changes
* `docs/<short-purpose>` — docs-only changes

**Conventional commits**

* `feat(core): add capability router`
* `fix(system): handle empty drift file`
* `chore(shared): bump pydantic floor`
* `docs(governance): add waiver example`

**Scopes** should map to domains (`core`, `agents`, `system`, `shared`, `data`), docs (`docs`, `governance`), or infrastructure (`deps`, `actions`).

---

## 3) Adding or Changing Capabilities

1. **Pick the right domain** in `.intent/knowledge/source_structure.yaml`.

2. Edit the domain manifest in `.intent/manifests/<domain>.manifest.json`:

   * Capabilities must be **unique** and **domain-prefixed** (e.g., `core:task-router`).

3. Run:

   ```bash
   make migrate              # scaffold + validate + duplicate check
   make guard-check          # enforce import boundaries
   make drift                # writes reports/drift_report.json
   ```

4. Implement code inside that domain only. Cross-domain calls go through core interfaces.

5. Update docs when behavior or rules change.

---

## 4) Dependency Policy

* Use **httpx** for HTTP. Do not use `requests` (forbidden by policy).
* Add third-party libs only if justified by architecture.
* Reflect allow-lists in:

  * `.intent/policies/intent_guard.yaml → rules.libraries.allowed`
  * `.intent/knowledge/source_structure.yaml → domain allowed_imports`

**Checklist for new deps:**

* Added to `pyproject.toml`
* Allowed in policy + source map (only where needed)
* No violations from `make guard-check`

---

## 5) Temporary Waivers (rare)

If you must defer a fix:

* Add a time-boxed waiver in `.intent/policies/intent_guard.yaml` under `enforcement.waivers`:

  ```yaml
  waivers:
    - path: "^src/system/legacy/.*\\.py$"
      reason: "Temporary while refactoring bootstrap"
      expires: "2025-12-31"
  ```

* Open an issue linking to the waiver.

* Plan a follow-up PR to remove it. **Goal: zero waivers.**

---

## 6) Local Checks (run before every PR)

```bash
# Governance
make migrate FAIL_ON_CONFLICTS=1
make guard-check
make drift

# Quality
make fast-check           # lint + tests
```

If you’re iterating fast and don’t want a failure to stop you:

```bash
poetry run core-admin guard check --no-fail
```

---

## 7) Definition of Done (DoD)

A PR is ready when:

* `.intent/` updates (if any) are consistent and validated
* `make migrate FAIL_ON_CONFLICTS=1` passes
* `make guard-check` shows no violations
* `make drift` generated **0 validation errors and 0 duplicate capabilities**
* `make fast-check` is green (lint + tests)
* Docs updated (`README` or `docs/`), including rationale for governance-relevant changes

---

## 8) PR Review Expectations

Reviewers will check:

* Constitution alignment (no cycles, correct domain imports)
* Capability uniqueness and accurate domain placement
* Library policy compliance (**httpx over requests**)
* Tests & lint
* Clear rationale in the PR description

---

## 9) CI Overview

Every push/PR runs:

* Manifest migration & validation (fails on duplicate capabilities)
* Intent Guard (import boundaries & library policy)
* Lint + tests

**Workflow:** `.github/workflows/guard-and-drift.yml`
**Artifacts:** `reports/drift_report.json` is attached to the run.

---

## 10) Security

* Report vulnerabilities privately (see `SECURITY.md`).
* Do not include secrets in PRs.

---

## 11) Questions

Open a GitHub Discussion or issue. For governance questions, reference:

* `.intent/policies/intent_guard.yaml`
* `.intent/knowledge/source_structure.yaml`
* `docs/03_GOVERNANCE.md`
