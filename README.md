# CORE — The Self-Improving System Architect

> **Where Intelligence Lives.**

CORE is a self-governing, constitutionally aligned AI development framework that can plan, write, validate, and evolve software systems — autonomously and safely. It is designed for environments where **trust, traceability, and governance matter**.

---

## 🧠 What CORE *is*

* 🛍️ A system that evolves itself through **declared intent**, not hidden assumptions
* 🛡️ A platform that enforces **constitutional rules**, **domain boundaries**, and **safety policies**
* 🧹 A modular agent architecture with **planner**, **reviewer**, **builder**, and **guardian** roles
* 📜 A framework where every decision is **documented, reversible, and introspectable**

---

## 🦮 Key Concepts

| Concept          | Description                                                                                          |
| ---------------- | ---------------------------------------------------------------------------------------------------- |
| `.intent/`       | The brain of CORE: contains purpose, governance rules, capability maps, and agent roles              |
| `PlannerAgent`   | Decides what changes should be made, and why                                                         |
| `PromptPipeline` | Structures LLM input/output with directives like `[[manifest:...]]`, `[[write:...]]`, `[[test:...]]` |
| `KnowledgeGraph` | Tracks symbols, roles, capabilities, and relationships across the codebase                           |
| `IntentGuard`    | Enforces boundaries and validates alignment with declared intent                                     |
| Git Rollback     | CORE can safely undo invalid changes via version-controlled write staging                            |
| Test Validator   | All changes must pass linting, formatting, syntax checks, and structured tests                       |

---

## 🚀 Getting Started

```bash
git clone https://github.com/YOUR_USERNAME/core.git
cd core
pip install -e .
cp .env.example .env
python -m core.main  # Launch the planner loop
```

Optional:

* Add your `.intent/` rules
* Provide a software goal or function manifest
* Watch CORE evolve itself

---

## 🔪 What CORE *does*

* Plans improvements using AI agents
* Generates code, tests, and docstrings
* Runs pre-flight validations (Black, Ruff, Pytest, AST)
* Self-corrects when validation fails
* Can revert broken commits automatically
* Logs every step for transparency

---

## 📌 Why CORE is Different

Unlike most auto-dev tools, CORE:

* Enforces **separation of duties** between agents
* Tracks **capabilities** per function/class with `# CAPABILITY:` tags
* Aligns all actions to **declared mission and values**
* Operates with **rollback, review, and validation by default**
* Supports **critical infrastructure** and **governance-heavy use cases**

---

## 🌱 Contributing

We welcome contributions from:

* AI engineers
* DevOps/GitOps pros
* Policy designers
* Governance/compliance experts

👉 See [`CONTRIBUTING.md`](CONTRIBUTING.md) to get started.
👉 Check out [Good First Issues](https://github.com/YOUR_USERNAME/core/issues?q=is%3Aopen+is%3Aissue+label%3A%22good+first+issue%22)

---

## 📄 License

This project is licensed under the **MIT License**. See [LICENSE](LICENSE) for details.

---

## 💡 Inspiration

CORE was born from a simple but powerful idea:
**"Software should not only work — it should know *why* it works, and who it’s working for."**

---

> “In the future, coding assistants won’t just autocomplete —
> they’ll *architect, align, enforce, and evolve*. CORE is that future, now.”
