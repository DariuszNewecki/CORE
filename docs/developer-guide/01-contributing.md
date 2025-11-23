# Contributing to CORE

Welcome to the CORE project.
This guide explains **how to contribute safely and correctly** within the Mind–Body–Will architecture and under the constraints of the `.intent/` constitution.

CORE is a *governed system*.
That means contributing is not just about writing code — it is about respecting:

* constitutional rules,
* autonomy boundaries,
* audit gates,
* knowledge integrity,
* stable IDs and capabilities.

This guide ensures your contributions strengthen the system rather than introduce drift.

---

# 1. Philosophy of Contribution

CORE is built on three principles:

### **1. Governance first**

No change may violate `.intent/` rules or bypass the Mind.

### **2. Transparency and traceability**

Every change must be inspectable, auditable, and explainable.

### **3. Autonomy within boundaries**

Agents may help generate code, but **humans remain responsible** for integrating and approving changes.

---

# 2. Repository Structure (What You Need to Know)

The CORE codebase uses the Mind–Body–Will architecture:

```
src/
├── api/            # HTTP API surface
├── body/           # CLI, actions, crate services
├── features/       # introspection, autonomy, self-healing, maintenance
├── mind/           # governance, auditor, policies
├── services/       # LLMs, DB, context building, validation pipelines
├── shared/         # utilities, config, common models
└── will/           # agents, orchestration, reasoning
```

You do **not** need to understand every subsystem to contribute, but you must understand:

* Mind controls the rules
* Body executes all actions
* Will proposes code, plans, and reasoning

---

# 3. Contribution Workflow

The CORE contribution workflow mirrors the governance model.

## 3.1. Step 1 — Create a Branch

Use clear names:

* `feature/xxx`
* `fix/xxx`
* `refactor/xxx`

Avoid mixing multiple changes.

---

## 3.2. Step 2 — Implement Changes

Write code normally in `src/`.

While developing:

* keep functions small and capability-scoped,
* maintain clean imports and domain boundaries,
* use docstrings for public-facing functions,
* avoid touching `.intent/` directly.

### ❗ Never modify `.intent/` manually.

If you believe a policy should change, submit a proposal (see Section 7).

---

## 3.3. Step 3 — Fix IDs and Metadata

Before committing, run:

```bash
poetry run core-admin fix ids --write
poetry run core-admin fix metadata --write   # if applicable
```

This ensures:

* stable ID tags,
* consistent metadata structure,
* correct capability attribution.

---

## 3.4. Step 4 — Sync Knowledge

CORE maintains its own self-knowledge.
After significant code changes, sync it:

```bash
poetry run core-admin manage database sync-knowledge
```

This rebuilds indexes, symbol tables, and capability mappings.

---

## 3.5. Step 5 — Run Audit Gate

Before committing code, always run:

```bash
poetry run core-admin check audit
```

The Constitutional Auditor checks:

* naming conventions,
* imports and boundaries,
* security rules,
* ID & capability hygiene,
* drift against Knowledge Graph,
* schema and manifest correctness.

If the auditor fails → fix the issues.
If you disagree with an audit finding → see Section 7.

---

## 3.6. Step 6 — Commit & Push

Only commit when:

* validation passes,
* audits pass,
* knowledge is synced,
* IDs and metadata are clean.

This protects the integrity of the system.

---

# 4. Using Autonomous Development as a Contributor

You may optionally use the autonomous developer to perform some changes.

For example:

```bash
poetry run core-admin develop feature "Add logging to capability registry"
```

CORE will:

* create a crate,
* generate code, tests, and docs inside it,
* validate content,
* run constitutional audits.

### Important:

The developer must still perform **manual integration** of generated code.

Never copy crates blindly.
Always review the AI’s output.

---

# 5. Writing Tests

When writing tests:

* place them under `tests/` mirroring the project structure,
* keep tests deterministic,
* avoid mocking higher-level governance components,
* test features, not implementation details,
* ensure tests never modify `.intent/`.

CORE’s self-healing tools can later generate missing tests autonomously.

---

# 6. Code Style

### Tools used:

* **Black** — formatting
* **Ruff** — linting
* **Pytest** — testing
* **YAML Validator** — schema correctness

You do not need to run formatters manually — the audit pipeline will include them.

But you may run:

```bash
poetry run core-admin fix code-style --write
```

---

# 7. Changing the Constitution (Advanced Contributors)

If you need to modify `.intent/`:

* update a policy,
* add a capability,
* adjust a governance rule,
* change architectural boundaries.

You must use the proposal workflow.

### 7.1. Create a proposal

```bash
poetry run core-admin manage proposals new "reason for change"
```

### 7.2. Sign it with an authorized key

```bash
poetry run core-admin keys keygen "your.email@example.com"
```

### 7.3. Run canary audit

CORE will apply the proposal to a temporary clone and audit it.

### 7.4. Submit for approval

Humans must approve or reject constitutional changes.

This protects CORE from accidental or unsafe evolution.

---

# 8. Principles for High-Quality Contributions

### 🔸 Small, atomic PRs

Make audits easier and reduce drift.

### 🔸 Follow architectural boundaries

Respect domain placement and imports.

### 🔸 Maintain capability hygiene

Every exported function/class should have a clear purpose.

### 🔸 Never work around audit findings

Fix the root cause or propose a constitutional change.

---

# 9. Getting Help

If you are unsure about:

* a failing audit,
* whether a change violates `.intent/`,
* how to structure a contribution,
* how autonomy affects your workflow,
* the proposal process,

ask in the CORE development channel or submit a draft PR for review.

---

# 10. Final Notes

Contributing to CORE means contributing to a **self-governing system**.
Every choice either strengthens or weakens the system’s long-term stability.

By following this document, you ensure:

* safe contributions,
* aligned evolution,
* consistent governance,
* trustworthy autonomous capabilities.

Thank you for helping build CORE.
