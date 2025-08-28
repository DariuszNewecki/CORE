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

👉 **[Run the Worked Example (`docs/09_WORKED_EXAMPLE.md`)](docs/09_WORKED_EXAMPLE.md)**

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

## Project Status & Independent Review

CORE is an **Architectural Prototype (v0.2.0)**, with a stable and functional governance loop. It has been independently reviewed by multiple AI assessors (Grok, ChatGPT) with a strong consensus:

* **Overall Score:** \~7.9 / 10
* **Key Strengths:** Governance & Safety (9/10), Documentation (8.5/10)
* **Next Steps:** Focus is on enhancing the AI reasoning layer and feature completeness.

The reviews confirm that CORE's foundation is exceptionally strong. The full reviews are archived in `docs/reviews/`.

---

## Documentation Portal

* **[What is CORE? (`docs/00_WHAT_IS_CORE.md`)](docs/00_WHAT_IS_CORE.md)** — The vision and philosophy.
* **[Architecture (`docs/02_ARCHITECTURE.md`)](docs/02_ARCHITECTURE.md)** — Technical details of the Mind and Body.
* **[Governance (`docs/03_GOVERNANCE.md`)](docs/03_GOVERNANCE.md)** — How changes are made safely.
* **[Roadmap (`docs/04_ROADMAP.md`)](docs/04_ROADMAP.md)** — See where we're going.
* **[Contributing (`CONTRIBUTING.md`)](CONTRIBUTING.md)** — Join our mission!

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
# Edit .env with your LLM API keys

# Verify setup is clean
make check

# Try the new conversational command!
poetry run core-admin chat "make me a simple command-line tool that prints a random number"
```

---

## Contributing

We welcome all contributors! The best place to start is our **Contributing Guide**.
Check the **Project Roadmap** for "Next Up" tasks and see our open issues on GitHub.

---

## License

MIT License — see `LICENSE`.
