# Starter Kits

Welcome to CORE. This guide provides **ready-to-use starter kits** that help you begin working with the system immediately.

Each kit reflects the **real CORE architecture** (Mind–Body–Will) and aligns with the governed development model.

Starter kits are meant to:

* give you minimal, functioning examples,
* show correct project structure,
* demonstrate safe workflows,
* and reduce onboarding friction.

---

# 1. What’s Included in Each Starter Kit

All starter kits include:

* a functional `src/` layout (api/body/features/mind/services/shared/will),
* minimal `.intent/` rules,
* example capabilities,
* basic constitutional policies,
* small demonstration tests,
* setup instructions,
* and safe defaults for development.

They are designed to be **extended**, not replaced.

---

# 2. Available Starter Kits

## 2.1. Minimal Project

The smallest possible valid CORE project.

Includes:

* a single route (`/hello`)
* one capability
* minimal `.intent/` with only required policies
* basic test suite
* full audit passing

Use when you want:

* to learn the structure,
* to experiment with autonomy,
* or to build a new project from scratch.

---

## 2.2. Feature-Driven Starter

Demonstrates using autonomy from day one.

Includes:

* example crates,
* autonomous feature generation workflow,
* tests showing crate acceptance criteria,
* explicit Mind–Body–Will demonstration.

Use when:

* showcasing CORE to others,
* bootstrapping a real project quickly.

---

## 2.3. Governance-Heavy Starter

Focused on `.intent/` and governance.

Includes:

* strong policies,
* additional schemas,
* stricter boundaries,
* example proposal workflows,
* domain segmentation.

Use for:

* enterprise governance demos,
* strict environments,
* deep governance experiments.

---

# 3. Getting Started with Any Kit

## 3.1. Install Dependencies

```bash
poetry install
```

## 3.2. Initialize Developer Secrets

```bash
poetry run core-admin secrets init
```

## 3.3. Run Initial Audit

```bash
poetry run core-admin check audit
```

This ensures your environment is ready.

## 3.4. Sync Knowledge

```bash
poetry run core-admin manage database sync-knowledge
```

Your environment is now fully initialized.

---

# 4. Using a Starter Kit with Autonomous Development

Once the kit is installed:

```bash
poetry run core-admin develop feature "Add health endpoint"
```

Then:

1. Inspect crate
2. Integrate manually
3. Self-heal
4. Sync knowledge
5. Audit

---

# 5. Next Steps

Continue with:

* `02-byor.md` — Bring Your Own Runtime
* `03-batch-mode.md`
* `04-secrets-management.md`

Or return to the Developer Guide:

* `../developer-guide/01-contributing.md`

Starter kits make CORE easy to adopt.
Everything else builds on the same governed foundations.
