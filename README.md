# CORE — The Self-Improving System Architect

> **Where Intelligence Lives.**

[![Status: Architectural Prototype](https://img.shields.io/badge/status-architectural%20prototype-blue.svg)](#-project-status)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![codecov](https://codecov.io/gh/DariuszNewecki/CORE/graph/badge.svg)](https://codecov.io/gh/DariuszNewecki/CORE)

CORE is a self-governing, constitutionally aligned AI development framework that can plan, write, validate, and evolve software systems — autonomously and safely. It is designed for environments where **trust, traceability, and governance matter**.

---

## 🏛️ Project Status: Architectural Prototype

The core self-governance and constitutional amendment loop is complete and stable. The system can audit and modify its own constitution via a human-in-the-loop, cryptographically signed approval process.

The next phase is to expand agent capabilities so CORE can generate and manage entirely new applications based on user intent. We’re making the project public now to invite collaboration on this foundational architecture.

---

## 🧠 What is CORE?

Traditional codebases often suffer from **architectural drift** — the code no longer matches the original design. Linters catch syntax errors, but architectural mistakes slip through.

CORE solves this by using a **“constitution”** (a set of machine-readable rules in `.intent/`) and an AI-powered **`ConstitutionalAuditor`** to ensure your code stays true to its design.

It’s built on a simple **Mind–Body–Will** philosophy:

* **Mind (`.intent/`)**: The Constitution. You declare your project's rules and goals here.
* **Body (`src/`)**: The Machinery. Simple, reliable tools that act on the code.
* **Will (AI Agents)**: The Reasoning Layer. AI agents that read the Mind and use the Body's tools to achieve your goals, while the Auditor ensures they never break the rules.

---

## 🚀 Getting Started (5-Minute Demo)

See CORE in action by running the worked example: create a simple API, intentionally break an architectural rule, and watch CORE's auditor catch it.

👉 **[Run the Worked Example (`docs/09_WORKED_EXAMPLE.md`)](docs/09_WORKED_EXAMPLE.md)**

---

## 📖 Documentation Portal

* **[What is CORE? (`docs/00_WHAT_IS_CORE.md`)](docs/00_WHAT_IS_CORE.md)** — The vision and philosophy.
* **[Architecture (`docs/02_ARCHITECTURE.md`)](docs/02_ARCHITECTURE.md)** — Technical details of the Mind and Body.
* **[Governance (`docs/03_GOVERNANCE.md`)](docs/03_GOVERNANCE.md)** — How changes are made safely.
* **[Roadmap (`docs/04_ROADMAP.md`)](docs/04_ROADMAP.md)** — See where we're going.
* **[Technical Debt Log (`docs/05_TECHNICAL_DEBT.md`)](docs/05_TECHNICAL_DEBT.md)** — Our formal plan for architectural improvements.
* **[Contributing (`CONTRIBUTING.md`)](CONTRIBUTING.md)** — Join our mission!

---

## ⚙️ Installation & Quick Start

**Requirements**: Python 3.12+, Poetry

```bash
# Clone and install
git clone https://github.com/DariuszNewecki/CORE.git
cd CORE
poetry install

# Set up environment
cp .env.example .env
# Edit .env with your LLM API keys

# Verify setup is clean by running the full system check
poetry run core-admin system check

# Try the conversational command!
poetry run core-admin chat "make me a simple command-line tool that prints a random number"

# 🌱 Contributing
We welcome all contributors! The best place to start is our Contributing Guide.

Check the Project Roadmap for "Next Up" tasks and see our open issues on GitHub.
# 📄 License
Licensed under the MIT License. See LICENSE.
