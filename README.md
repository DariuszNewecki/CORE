# CORE — Architectural Integrity for AI-Era Development

CORE ensures your code stays true to your project’s design, using AI to catch architectural violations and guide safe, governed development.

---

## Why CORE?

Codebases often drift from their intended design:

* New features ignore established patterns.
* Modules import dependencies they shouldn’t.
* Documentation becomes outdated.
* Reviews miss big-picture issues.

Linters catch syntax errors, but architectural mistakes slip through.
**CORE** uses a **“constitution”** (rules in `.intent/`) and **AI-powered auditing** to keep your project on track.

---

## CORE in 30 Seconds

1. **Set Rules**: Define your project’s architecture in `.intent/` (e.g., which modules can talk to each other).
2. **Write Code**: Build your app as usual in `src/`.
3. **Audit**: Run `make audit` to check if code follows rules.
4. **Fix**: Get clear feedback with fixes (e.g., *“Move this import to a service layer”*).

### Example Audit Output

```
❌ Violation: src/api/user.py
   Issue: 'api' imported 'database.models'
   Rule: API layer only imports 'services'
   Fix: Use UserService for database logic
```

---

## Try It Out (5-Minute Demo)

See CORE in action with the worked example:

1. Create a **“Quote of the Day” API**.
2. Break a rule (e.g., add a forbidden import).
3. Watch CORE catch it and suggest a fix.

---

## Visualizing CORE

CORE’s **Mind–Body–Will** model ensures governance:

```
+-----------------+
| Mind (.intent/) | Rules & Principles (YAML/JSON)
+-----------------+
          |
          v
+-----------------+
| Will (AI Agents)| Plans & Generates Code
+-----------------+
          |
          v
+-----------------+
| Body (src/)     | Your Codebase
+-----------------+
          |
          v
[Auditor] Ensures code aligns with rules
```

---

## Glossary

* **Mind**: Rules in `.intent/` (e.g., domain boundaries).
* **Body**: Your code in `src/`.
* **Will**: AI agents that plan and write code.
* **Auditor**: Checks code against rules, with safe “canary” tests for changes.

---

## Installation & Quick Start

**Requirements**: Python 3.12+, Poetry, Git

```bash
# Clone and install
git clone https://github.com/DariuszNewecki/CORE.git
cd CORE
poetry install

# Set up environment
cp .env.example .env
# Edit .env with LLM API keys (see .intent/config/runtime_requirements.yaml)

# Verify setup
make check

# Create a governed project
poetry run core-admin new my-app --profile default

# Run an audit
cd work/my-app && make audit
```

### Troubleshooting

* **Poetry errors?** Run `poetry shell` or prefix with `poetry run`.
* **Audit fails?** Check `reports/drift_report.json` for details.
* **Need keys?** See `.intent/config/runtime_requirements.yaml`.

---

## When to Use CORE

Perfect for:

* Teams building complex systems (e.g., microservices, enterprise apps).
* Projects needing traceable, auditable changes.
* Developers using AI safely with governance.

Not ideal for:

* Simple scripts or one-off prototypes.
* Teams relying only on manual reviews.

---

## Real-World Example

Turn a Flask app into a governed project:

```bash
# Initialize governance in an existing app
poetry run core-admin byor-init /path/to/flask-app --write
```

* Get a `.intent/` directory with rules (e.g., “API only imports services”).
* Run `make audit` to ensure compliance.

---

## How It Works

* **Mind (.intent/):** YAML/JSON files define rules, like domain boundaries or safety policies.
* **Body (src/):** Your code, organized into domains (e.g., core, agents).
* **Will (AI):** Agents (e.g., PlannerAgent) generate code within rules.
* **Auditor:** Checks for violations (e.g., illegal imports) and suggests fixes.

Changes are secured with **cryptographic signatures** and **“canary checks”** (testing changes in isolation).

---

## Project Status

CORE is an **Architectural Prototype (v0.2.0)**, stable for auditing and governance.
It’s at **A0 (Observe)** on the Autonomy Ladder, moving toward **A1 (Propose)** by generating safe PRs.

**Next steps**: autonomous app creation (see *Roadmap*).

Join us to shape AI-driven development!

---

## Documentation

* **What is CORE?**: Philosophy and vision.
* **Architecture**: Technical details.
* **Governance**: How changes are made safely.
* **Starter Kits**: Templates for new projects.
* **Contributing**: How to get involved.

---

## Comparison to Other Tools

| Tool            | Purpose              | CORE’s Edge                         |
| --------------- | -------------------- | ----------------------------------- |
| ESLint / Pylint | Syntax checking      | Enforces architectural rules        |
| SonarQube       | Code quality metrics | Traceable, governed changes         |
| ArchUnit        | Architecture testing | AI-driven analysis with clear fixes |
| GitHub Copilot  | Code completion      | Governed, safe AI code generation   |
| AutoGPT         | Autonomous tasks     | Structured, auditable code changes  |

**CORE is an AI architect, ensuring maintainability and safety.**

---

## Contributing

We welcome all contributors! See `CONTRIBUTING.md` for details. Help with:

* AI agents (e.g., autonomous code generation).
* Safety policies or starter kits.
* Docs or sample apps (e.g., a REST API).

**Quick Start:** Fix a docstring or run `make audit` on a sample project.

---

## License

MIT License — see `LICENSE`.
