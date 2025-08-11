# ./docs/06\_STARTER\_KITS.md

# 6. Starter Kits & The Philosophy of Intent

## The CORE Partnership

CORE is not a vending machine for code. It is an intelligent partner designed to translate a human's intent into a governed, working software system. This partnership requires two things:

1. **The Human's Responsibility:** Provide a clear, high-level intent—the "why" behind the project.
2. **CORE's Responsibility:** Translate that intent into a complete system, asking for clarification and guidance along the way.

If the human provides no intent ("I do not care"), CORE will do nothing. The partnership requires a starting point.

## Starter Kits: Your First Declaration of Intent

To facilitate this partnership, the `core-admin new` command uses **Starter Kits**. A starter kit is not just a collection of template files; it is a **pre-packaged declaration of intent**. It is a way for you to tell CORE about the *kind* of system you want to build from day one.

By choosing a starter kit, you are providing the "minimal viable intent" that CORE needs to begin its work.

### How to Use Starter Kits

When you create a new project, you can specify a `--profile` option. This tells the scaffolder which starter kit to use.

```bash
# Scaffold a new project using the 'default' balanced starter kit
poetry run core-admin new my-new-app --profile default

# Scaffold a project with high-security policies from the start
poetry run core-admin new my-secure-api --profile security
```

If you do not provide a profile, CORE will default to the safest, most balanced option.

## The Life of a Starter Kit

* **Scaffolding:** CORE creates your new project structure and populates the `.intent/` directory with the constitutional files from your chosen starter kit.
* **Ownership:** From that moment on, that constitution is **yours**. It is no longer a template. It is the living "Mind" of your new project.
* **Evolution:** You can (and should) immediately begin to amend and evolve your new constitution to perfectly match your project's unique goals, using the standard proposals workflow.

Starter kits are just the beginning of the conversation, not the end. They are the most effective way to kickstart the CORE partnership and begin the journey of building a truly intent-driven system.

---

# ./README.md

# CORE — The Self-Improving System Architect

> **Where Intelligence Lives.**

[![Status: Architectural Prototype](https://img.shields.io/badge/status-architectural%20prototype-blue.svg)](#-project-status)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

CORE is a self-governing, constitutionally aligned AI development framework that can plan, write, validate, and evolve software systems — autonomously and safely. It is designed for environments where **trust, traceability, and governance matter**.

---

## 🏛️ Project Status: Architectural Prototype

The core self-governance and constitutional amendment loop is complete and stable. The system can audit and modify its own constitution via a human-in-the-loop, cryptographically signed approval process.

The next phase, as outlined in our **[Strategic Plan](docs/StrategicPlan.md)**, is to expand agent capabilities so CORE can generate and manage entirely new applications based on user intent.

We’re making the project public now to invite collaboration on this foundational architecture.

---

## 🧠 What CORE *is*

* 🧾 Evolves itself through **declared intent**, not hidden assumptions.
* 🛡️ Enforces **constitutional rules**, **domain boundaries**, and **safety policies**.
* 🌱 Creates new, governed applications from **[Starter Kits](docs/06_STARTER_KITS.md)** that capture initial intent.
* 🧩 Uses a modular agent architecture with a clear separation of concerns.
* 📚 Ensures every decision is **documented, reversible, and introspectable**.

---

## 🦮 Key Concepts

| Concept                     | Description                                                                              |
| --------------------------- | ---------------------------------------------------------------------------------------- |
| **`.intent/`**              | The “mind” of CORE: constitution, policies, capability maps, and self-knowledge.         |
| **`ConstitutionalAuditor`** | The “immune system,” continuously verifying code aligns with the constitution.           |
| **`PlannerAgent`**          | Decomposes high-level goals into executable plans.                                       |
| **`core-admin` CLI**        | Human-in-the-loop tool for managing the system's lifecycle.                              |
| **Starter Kits**            | Pre-packaged constitutions that serve as the user's first declaration of intent.         |
| **Canary Check**            | Applies proposed changes to an isolated copy and runs a full self-audit before approval. |
| **Knowledge Graph**         | Machine-readable map of symbols, roles, capabilities, and relationships.                 |

---

## 🚀 Getting Started

1. **Install dependencies**

   ```bash
   poetry install
   ```

2. **Set up environment**

   ```bash
   cp .env.example .env
   # Edit .env with your keys/URLs. See .intent/config/runtime_requirements.yaml for required variables.
   ```

3. **Run a full self-audit**

   ```bash
   make audit
   ```

---

## 🧑‍⚖️ Human-in-the-Loop (CLI)

The `core-admin` CLI is your primary tool for guiding the system.

### Creating New Projects

```bash
# Create a new, governed application using a starter kit
core-admin new my-new-app --profile default
```

### Onboarding Existing Projects

```bash
# Analyze an existing repo and propose a starter constitution
core-admin byor-init /path/to/existing-repo
```

### Managing the Constitution

```bash
# List pending constitutional changes
core-admin proposals-list

# Sign a proposal with your key
core-admin proposals-sign cr-example.yaml

# Approve a proposal (runs a canary self-audit)
core-admin proposals-approve cr-example.yaml
```

> If `core-admin` isn’t found, try: `poetry run core-admin ...`

---

## 🌱 Contributing

We welcome contributions from AI engineers, DevOps pros, and governance experts.

* See **CONTRIBUTING.md** to get started.
* Check the **Strategic Plan** for where we're headed.

---

## 📄 License

Licensed under the MIT License. See **LICENSE**.
