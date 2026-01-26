# Contributing to CORE

CORE is a **constitution-driven system**.

All contributions must respect and preserve the project’s constitutional model,
defined in the `.intent/` directory.

If you have not read `.intent/`, you are **not ready to contribute**.

---

## CORE First Principle: The Constitution

The `.intent/` directory contains CORE’s Constitution:
- architectural rules
- governance constraints
- enforcement mappings
- system invariants

These rules are **authoritative**.

Code, tests, and tooling must comply with the Constitution — not the other way around.

Changes that violate constitutional intent will be rejected, even if they pass CI.

---

## Contribution Rules

### 1. Read Before You Write
Before opening a PR, contributors are expected to:
- Review relevant files in `.intent/`
- Understand which rules apply to the area being changed

If a change impacts governance, architecture, or enforcement logic,
this **must be explicitly stated** in the PR description.

---

### 2. Pull Requests Only
All changes must go through a Pull Request.
Direct pushes to `main` are not allowed.

Keep PRs:
- small
- focused
- traceable to intent

---

### 3. Dependency Updates
Automated dependency updates (e.g. Dependabot) are allowed.

Rules:
- Low-risk updates may be merged if CI passes
- Framework, runtime, or governance-relevant updates require manual review
- No dependency update may weaken constitutional enforcement

---

### 4. CI Is Necessary, Not Sufficient
CI currently performs smoke testing.

Passing CI **does not guarantee** constitutional correctness.
Maintainers may reject PRs that pass CI but violate intent.

---

### 5. Code Quality Expectations
- Follow existing structure and patterns
- Do not introduce new architectural concepts casually
- Avoid speculative refactors

If `pre-commit` hooks exist, contributors are expected to run them locally.

---

## What Is Not Acceptable
- Changes that bypass or dilute `.intent/`
- Introducing behavior that contradicts declared intent
- “It works” as justification for architectural violations
- Force-pushes to shared branches

---

## Unsure?
If you are unsure whether a change aligns with CORE’s Constitution:
**open an issue or discussion first**.

Intent clarification is always preferred over corrective cleanup.

---

CORE is governed by intent.
Thank you for respecting it.
