# CORE — The Self-Improving System Architect

> **Where Intelligence Lives.**

[![Status: MVP Achieved](https://img.shields.io/badge/status-MVP%20achieved-brightgreen.svg)](#-project-status)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

CORE is a self-governing, constitutionally aligned AI development framework that can plan, write, validate, and evolve software systems — autonomously and safely. It is designed for environments where **trust, traceability, and governance matter**.

---

## 🏛️ Project Status: MVP Achieved

The core self-governance loop is stable, and the system has achieved its MVP goal: the ability to autonomously generate a new, working, and constitutionally-governed application from a high-level user goal.

The next phase, as outlined in our **[Project Roadmap](docs/04_ROADMAP.md)**, is to expand the complexity of applications CORE can generate and enhance its agentic reasoning.

---

## 🧠 What CORE *is*

* 🧾 Evolves itself through **declared intent**, not hidden assumptions.
* 🛡️ Enforces **constitutional rules**, **domain boundaries**, and **safety policies**.
* 🌱 Creates new, governed applications from **[Starter Kits](docs/06_STARTER_KITS.md)** that capture initial intent.
* 🧩 Uses a modular agent architecture with a clear separation of concerns.
* 📚 Ensures every decision is **documented, reversible, and introspectable**.

---

## 🦮 Key Concepts

| Concept                                                                 | Description                                                                                 |
| ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| **`.intent/`**                                                          | The “mind” of CORE: constitution, policies, capability maps, and self-knowledge.            |
| **`ConstitutionalAuditor`**                                             | The “immune system,” continuously verifying code aligns with the constitution.              |
| **`PlannerAgent`**                                                      | Decomposes high-level goals into executable plans.                                          |
| **`core-admin` CLI**                                                    | Human-in-the-loop tool for managing the system's lifecycle.                                 |
| **[Constitutional Peer Review](docs/07_CONSTITUTIONAL_PEER_REVIEW.md)** | Uses an external LLM to critique and suggest improvements to the system's own constitution. |
| **Starter Kits**                                                        | Pre-packaged constitutions that serve as the user's first declaration of intent.            |
| **Canary Check**                                                        | Applies proposed changes to an isolated copy and runs a full self-audit before approval.    |
| **Knowledge Graph**                                                     | Machine-readable map of symbols, roles, capabilities, and relationships.                    |

---

## 🚀 Getting Started

1. **Install dependencies**

   ```bash
   poetry install
   ```

2. **Set up environment**

   ```bash
   cp .env.example .env
   # Edit .env with your keys/URLs.
   # See .intent/config/runtime_requirements.yaml for required variables.
   ```

3. **Run a full self-audit**

   ```bash
   make check
   ```

4. **Human-in-the-Loop (CLI)** — `core-admin` is your primary tool for guiding the system.

   **Autonomous Application Generation (The MVP)**

   ```bash
   # Autonomously generate a new application in the 'work/' directory
   poetry run core-admin agent scaffold "my-new-app" "a simple flask web server"
   ```

   **Creating New Projects (Manual)**

   ```bash
   # Create a new, governed application using a starter kit
   core-admin new my-new-app --profile default
   ```

   **Onboarding Existing Projects**

   ```bash
   # Analyze an existing repo and propose a starter constitution
   core-admin byor-init /path/to/existing-repo
   ```

   **Managing the Constitution**

   ```bash
   # List pending constitutional changes
   core-admin proposals list

   # Sign a proposal with your key
   core-admin proposals sign cr-example.yaml

   # Approve a proposal (runs a canary self-audit)
   core-admin proposals approve cr-example.yaml
   ```

   > If `core-admin` isn’t found, prefix with: `poetry run core-admin ...`

---

## 🌱 Contributing

We welcome contributions from AI engineers, DevOps pros, and governance experts.

* See **CONTRIBUTING.md** to get started.
* Check the **Project Roadmap** for where we're headed.

---

## 📄 License

Licensed under the **MIT License**. See `LICENSE`.