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

* 🧾 Evolves itself through **declared intent**, not hidden assumptions
* 🛡️ Enforces **constitutional rules**, **domain boundaries**, and **safety policies**
* 🧩 Uses a modular agent architecture with a clear separation of concerns
* 📚 Ensures every decision is **documented, reversible, and introspectable**

---

## 🦮 Key Concepts

| Concept                     | Description                                                                              |
| --------------------------- | ---------------------------------------------------------------------------------------- |
| **`.intent/`**              | The “mind” of CORE: constitution, policies, capability maps, and self-knowledge.         |
| **`ConstitutionalAuditor`** | The “immune system,” continuously verifying code aligns with the constitution.           |
| **`PlannerAgent`**          | Decomposes high-level goals into executable plans.                                       |
| **`core-admin` CLI**        | Human-in-the-loop tool for signing and ratifying constitutional changes.                 |
| **Canary Check**            | Applies proposed changes to an isolated copy and runs a full self-audit before approval. |
| **Knowledge Graph**         | Machine-readable map of symbols, roles, capabilities, and relationships.                 |
| **Git & Rollback**          | Everything is versioned; invalid changes can be safely rolled back.                      |

---

## ⚙️ Requirements

* Python **3.9+**
* [Poetry](https://python-poetry.org/) for dependency & venv management
* Optional: `ruff`, `black` (installed via Poetry), `uvicorn` for the API server

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

3. **Quick validation (governance)**

```bash
# Generate a knowledge-graph artifact (used by strict checks)
core-admin guard kg-export

# Detect capability drift between .intent manifest and code (strict mode)
core-admin guard drift --strict-intent --format pretty
# or JSON for machines/CI:
core-admin guard drift --strict-intent --format json
```

4. **Run the server (optional)**

```bash
make run
# FastAPI docs at: http://localhost:8000/docs
```

---

## 🧑‍⚖️ Human-in-the-Loop (CLI)

Constitutional changes are proposed as files under `.intent/proposals/` and managed via the `core-admin` CLI.

```bash
# List pending proposals
core-admin proposals-list

# Sign a proposal with your generated key
core-admin proposals-sign cr-example.yaml

# Approve a proposal (runs canary self-audit in isolation)
core-admin proposals-approve cr-example.yaml

# Generate a new key pair for a new contributor
core-admin keygen "name@example.com"
```

> If `core-admin` isn’t found, try: `poetry run core-admin ...`

---

## ✅ Validation Tools (Operator & CI)

### Capability Drift (source of truth = `.intent/`)

* Compares declared capabilities in `.intent/*manifest*.yaml` with capabilities discovered in code (via Knowledge Graph or tagged comments).
* **Strict mode** requires a KG artifact or live builder; it won’t “guess”.

**Typical flow**

```bash
core-admin guard kg-export
core-admin guard drift --strict-intent --format pretty
```

**Evidence**

* A machine-readable JSON report is written to `reports/drift_report.json`.

**Output UX defaults (human-friendly)**

* By default, you’ll see a colored summary with **NONE** for empty sections and a clear ✅ or 🚨 status.
* JSON remains available for CI.

These defaults are governed by `.intent` (see below).

---

## 📝 UX Defaults Governed by `.intent/`

Place this block in `.intent/project_manifest.yaml` to make operator behavior explicit and predictable for anyone (human or agent):

```yaml
operator_experience:
  guard:
    drift:
      default_format: pretty        # pretty | table | json
      default_fail_on: any          # any | missing | undeclared
      strict_default: true          # require KG/artifact by default
      evidence_json: true           # always write JSON evidence
      evidence_path: reports/drift_report.json
      labels:
        none: "NONE"
        success: "✅ No capability drift"
        failure: "🚨 Drift detected"
```

> Change `default_format` to `json` if you prefer raw JSON by default.

---

## 🔪 What CORE *does*

* Plans improvements using AI agents
* Generates code, tests, and docstrings
* **Self-audits** to ensure constitutional alignment
* **Governs self-modification** via signed proposals + canary checks
* Self-corrects when validation fails
* Logs every step for transparency

---

## 🌌 North Star

CORE’s long-term aim is **A5 autonomy**: turn goals into governed code and running systems, safely and without human intervention in low-risk areas.
See **[NORTH\_STAR](docs/NORTH_STAR.md)** and **[BYOR](docs/05_BYOR.md)** for how CORE applies the same rules to any repo — including itself.

---

## 🧰 Troubleshooting

* **Strict mode error about missing capabilities**

  * Run `core-admin guard kg-export` first (or disable strict mode).
* **CLI not found**

  * Use `poetry run core-admin ...`
* **Drift report not in expected folder**

  * Reports are written under the repo root: `reports/`. You can change the path in `.intent` (`evidence_path`).

---

## 📌 Why CORE is Different

* **Separation of duties** between agents and roles
* **Capability tags** (`# CAPABILITY:`) at the function/class level
* A **declared, auditable constitution** that governs behavior
* **Rollback, review, and cryptographic validation by default**
* Built for **governance-heavy** and **safety-critical** contexts

---

## 🌱 Contributing

We welcome contributions from:

* AI engineers
* DevOps/GitOps pros
* Policy designers
* Governance/compliance experts

👉 See **[`CONTRIBUTING.md`](CONTRIBUTING.md)** to get started.
👉 Check the **[Strategic Plan](docs/StrategicPlan.md)** for where we're headed.

---

## 📄 License

Licensed under the **MIT License**. See **[LICENSE](LICENSE)**.

---

## 💡 Inspiration

CORE was born from a simple but powerful idea:
**“Software should not only work — it should know *why* it works, and who it’s working for.”**
