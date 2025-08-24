# CORE — The Self-Governing System Architect

> **Where Intelligence Lives.**

![Status: Architectural Prototype](https://img.shields.io/badge/status-architectural%20prototype-blue.svg)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**CORE is an AI-driven framework that builds and evolves software in constant alignment with a machine-readable constitution.**
It helps you turn high-level goals into safe, traceable, and architecturally sound applications.

---

## The 5-Minute "Aha!" Moment

The best way to understand CORE is to see its "immune system" in action.

**[➡️ Start here: Your First Governed Application (A 5-min Tutorial)](docs/09_WORKED_EXAMPLE.md)**

This tutorial will guide you through:

1. Generating a new, governed application with a single command.
2. Intentionally violating its architectural rules.
3. Watching CORE's `ConstitutionalAuditor` instantly detect and report the violation.

---

## What is This For? (The Vision)

CORE is for developers and teams who need to enforce architectural integrity and maintain long-term alignment with a project's goals, especially in complex or AI-driven systems. It solves the problem of **architectural drift**, where the code no longer matches the design.

* To understand the philosophy, read **[What is CORE?](docs/00_WHAT_IS_CORE.md)**.
* To see how it's different from other tools, read **[Context and Comparisons](docs/08_CONTEXT_AND_COMPARISONS.md)**.

---

## Installation & Setup

> Requires **Python 3.11+** and **Poetry**.

```bash
# 1. Clone & Install
git clone https://github.com/DariuszNewecki/CORE.git
cd CORE
poetry install

# 2. Set Up Environment
cp .env.example .env
# Edit .env with your LLM API keys.

# 3. Verify the System is Healthy
make check
```

---

## Contributing

We welcome focused, high-quality contributions.
Please read **CONTRIBUTING.md** to get started.

---

## License

MIT — see **LICENSE**.
