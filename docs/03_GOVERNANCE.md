# Governance & Enforcement Guide

> **Constitution = `.intent/`**. Everything else conforms to it.

## 1. What lives where

* **Index:** `.intent/meta.yaml`
* **Policies:** `.intent/policies/intent_guard.yaml`
* **Domain map:** `.intent/knowledge/source_structure.yaml`
* **Manifest schema:** `.intent/schemas/manifest.schema.json`
* **Domain manifests:** `.intent/manifests/*.manifest.json`
* **Drift evidence:** `reports/drift_report.json` (auto-generated)

## 2. Daily workflow (short)

1. **Scaffold & validate manifests**

   ```bash
   make manifests-scaffold
   make manifests-validate
   make manifests-dups         # set FAIL_ON_CONFLICTS=1 to enforce
   ```

2. **Generate drift evidence & view**

   ```bash
   make drift                   # writes reports/drift_report.json and prints a summary
   ```

3. **Run guard checks (imports/boundaries)**

   ```bash
   make guard-check             # pretty table output
   PYTHONPATH=src poetry run core-admin guard check --format=json --no-fail
   ```

4. **Run tests & quality**

   ```bash
   make fast-check              # lint + tests
   make check                   # lint + tests + audit
   ```

## 3. Adding or changing capabilities

* Pick the right **domain** (see “allowed imports” in `source_structure.yaml`).
* Update its manifest in `.intent/manifests/<domain>.manifest.json`.
* Keep capability names **unique** and **domain‑prefixed** (e.g., `core:task-router`).
* Re-run:

  ```bash
  make migrate                  # scaffold + validate + duplicate check in one go
  make guard-check
  ```
* Implement code **inside that domain only**. For cross-domain calls, go through **core interfaces**.

## 4. Rules you must not break

* **No cycles** between domains.
* **Default deny**: if a domain pair isn’t explicitly allowed, it’s not allowed.
* **Agents → system** is **forbidden** (system may import agents, not the other way).
* **Core → data** is **forbidden** (Dependency Inversion: data implements core ports).
* **Networking:** use `httpx` (not `requests`). The policy forbids `requests`.
* If you hit a rule during a refactor and need temporary relief, add a **waiver** in `intent_guard.yaml` **with an expiry date**. Keep waivers rare and short‑lived.

## 5. Troubleshooting (common failures)

* **“may not import” error**
  You imported across domains without permission. Move code or introduce a core interface.

* **“forbidden-library 'requests'”**
  Replace with `httpx`. Don’t add `requests` to dependencies.

* **Schema validation errors**
  Fix the manifest to match `.intent/schemas/manifest.schema.json`. Ensure `capabilities` is a **non-empty array** with **unique strings**.

* **Duplicate capabilities**
  Rename or consolidate; a capability must belong to **one** domain.

## 6. CI recommendation (optional snippet)

Add a job that fails on drift or guard violations:

```bash
make migrate FAIL_ON_CONFLICTS=1
PYTHONPATH=src poetry run core-admin guard check
```

## 7. Glossary

* **Drift:** schema errors or duplicate capabilities across manifests.
* **Guard:** static checks enforcing domain boundaries & library policy.
* **Constitution:** `.intent/` directory; source of truth for governance.
