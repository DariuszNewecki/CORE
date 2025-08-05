# CORE — The Self-Improving System Architect

> **Where Intelligence Lives.**

[![Status: Architectural Prototype](https://img.shields.io/badge/status-architectural%20prototype-blue.svg)](#-project-status)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

CORE is a self-governing, constitutionally aligned AI development framework that can plan, write, validate, and evolve software systems — autonomously and safely. It is designed for environments where **trust, traceability, and governance matter**.

---

## 🏛️ Project Status: Architectural Prototype

The core self-governance and constitutional amendment loop is complete and stable. The system can successfully audit and modify its own constitution in a secure, principled way using a human-in-the-loop, cryptographically signed approval process.

The next major phase of development, as outlined in our **[Strategic Plan](docs/StrategicPlan.md)**, is to build the agent capabilities that will allow CORE to generate and manage entirely new applications based on user intent.

We are making the project public now to invite collaboration on this foundational architecture.

---

## 🧠 What CORE *is*

*   🛍️ A system that evolves itself through **declared intent**, not hidden assumptions
*   🛡️ A platform that enforces **constitutional rules**, **domain boundaries**, and **safety policies**
*   🧹 A modular agent architecture with a clear separation of concerns
*   📜 A framework where every decision is **documented, reversible, and introspectable**

---

## 🦮 Key Concepts

| Concept | Description |
|---|---|
| **`.intent/`** | The "mind" of CORE: contains the constitution, policies, capability maps, and self-knowledge. |
| **`ConstitutionalAuditor`** | The system's "immune system," which continuously verifies that the code aligns with the constitution. |
| **`PlannerAgent`** | The primary AI agent that decomposes high-level goals into executable plans. |
| **`core-admin` CLI** | The secure, human-in-the-loop tool for ratifying constitutional changes. |
| **Canary Check** | A safety mechanism where proposed changes are audited in an isolated "what-if" environment before being applied. |
| **Knowledge Graph** | Tracks symbols, roles, capabilities, and relationships across the codebase. |
| **Git & Rollback** | All changes are version-controlled, and the system is designed for safe rollback of invalid modifications. |

---

## 🚀 Getting Started

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/YOUR_USERNAME/core.git
    cd core
    ```
2.  **Install dependencies:**
    ```bash
    poetry install
    ```
3.  **Set up your environment:**
    ```bash
    cp .env.example .env
    # Edit .env with your API keys and paths. See .intent/config/runtime_requirements.yaml for all required variables.
    ```
4.  **Run the self-audit:**
    Before running the system, verify that your local setup is constitutionally valid.
    ```bash
    python -m src.core.capabilities
    ```
    The expected output is `✅ ALL CHECKS PASSED (0 warnings)`.

5.  **Launch the CORE server:**
    ```bash
    make run
    ```

---

## 🔪 What CORE *does*

*   Plans improvements using AI agents.
*   Generates code, tests, and docstrings.
*   **Performs self-audits** to ensure constitutional alignment.
*   **Enforces a secure, human-approved process for self-modification.**
*   Self-corrects when validation fails.
*   Logs every step for transparency.

---

## 📌 Why CORE is Different

Unlike most auto-dev tools, CORE:

*   Enforces **separation of duties** between agents and roles.
*   Tracks **capabilities** per function/class with `# CAPABILITY:` tags.
*   Aligns all actions to a **declared and auditable constitution**.
*   Operates with **rollback, review, and cryptographic validation by default**.
*   Supports **critical infrastructure** and **governance-heavy use cases**.

---

## 🌱 Contributing

We welcome contributions from:

*   AI engineers
*   DevOps/GitOps pros
*   Policy designers
*   Governance/compliance experts

👉 See **[`CONTRIBUTING.md`](CONTRIBUTING.md)** to get started.
👉 Check out our **[Project Roadmap](docs/StrategicPlan.md)** to see where we're headed.

---

## 📄 License

This project is licensed under the **MIT License**. See the **[LICENSE](LICENSE)** file for details.

---

## 💡 Inspiration

CORE was born from a simple but powerful idea:
**"Software should not only work — it should know *why* it works, and who it’s working for."**