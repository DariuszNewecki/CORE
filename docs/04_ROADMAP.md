# The CORE Project Roadmap

## For New Users: Where CORE Is Going

CORE is evolving from a system that audits code (**A0**) into a conversational AI architect (**A4**) that builds apps from your ideas. The foundational governance layer is complete.

Our roadmap is now focused on two major epics:
1.  **v1.0: The Self-Evolving Architect** - Making the system's AI reasoning smarter and more efficient.
2.  **v1.1: The Accessible Operator** - Unifying all commands into a single, user-friendly CLI with an interactive menu.

👉 **You can help!** Check out the **Next Up** phase in the tables below for great contribution opportunities.

---

## Preamble: From Foundation to Self-Evolution

*   The project has a stable foundation for audits and governance.
*   The core logic for the policy-driven AI layer (**Mind/Body/Will**) is implemented.
*   With the completion of the conversational chat command, the system can now translate natural language into structured goals.
*   The next steps focus on making the system's reasoning more dynamic and its user interface more accessible.

📄 **Historical work:** [`docs/archive/StrategicPlan.md`](docs/archive/StrategicPlan.md)

---

## Epic v1.0: The Self-Evolving Architect

**Goal:** Build a self-evolving system that understands non-coders’ ideas and optimizes AI usage without hardcoded limits.

### Roadmap Phases (v1.0)

| Phase | Challenge | Goal | Status | Opportunity | ETA |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1: Constitution | Implicit AI roles in code | Define `cognitive_roles.yaml` for roles like Planner, Coder | ✅ Completed | Refine roles or propose new specialized agents (e.g., TestWriter). | Completed Q3 2024 |
| 2: Machinery | Body has AI logic | Build simple `CognitiveService` to read roles | ✅ Completed | Optimize the CognitiveService for performance or caching. | Completed Q3 2024 |
| 3: Agents | Agents use hardcoded clients | Refactor agents to use `CognitiveService` | ✅ Completed | Improve the agent reasoning loop in `run_development_cycle`. | Completed Q3 2024 |
| 4: Cleanup | Obsolete classes | Remove old `BaseLLMClient`; update `runtime_requirements.yaml` | ⏳ Planned | A great first-time contributor task to remove `src/core/clients.py`. | Q4 2024 |
| 5: Conversational Access | CLI limits non-coders | Add `IntentTranslator` agent and core-admin chat command | ✅ Completed | Improve the `intent_translator.prompt` for more complex queries. | Completed Q3 2024 |
| 6: Dynamic Deduction | Static LLM assignments | Add `DeductionAgent` + policy to optimize LLM choices | ▶️ **Next Up** | Propose `deduction_policy.yaml`; design and code the scoring logic. | Q1 2025 |

---

## Epic v1.1: The Accessible Operator

**Goal:** Dramatically improve the accessibility and discoverability of CORE's capabilities by unifying all user actions into a single `core-admin` entrypoint with an optional interactive menu.

### Roadmap Phases (v1.1)

| Phase | Challenge | Goal | Status | Opportunity | ETA |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1: Consolidation | Multiple entry points (`make`, `poetry run`) | Migrate all `Makefile` logic into scriptable `core-admin system` commands. | ⏳ Planned | Help create the new CLI commands (e.g., `system check`). | Q2 2025 |
| 2: Discoverability | Poor command visibility | Implement a richly formatted, grouped help screen for `core-admin --help`. | ⏳ Planned | Design the layout and grouping for the new help text. | Q2 2025 |
| 3: Accessibility | High cognitive load for new users | Build an interactive, menu-driven TUI that launches on `core-admin`. | 💡 **Idea** | Research TUI libraries like `rich` or `questionary`. | Q2 2025 |
| 4: API Clarity | Undefined API purpose | Create `docs/10_API_REFERENCE.md` to formalize the API for machine use. | ⏳ Planned | A great documentation task for a beginner. | Q2 2025 |

---

## Future Phases (Post-v1.1)

| Phase | Goal | ETA |
| :--- | :--- | :--- |
| Web Interface & DB | Evolve the unified CLI/API to a web UI with DB backing for full accessibility. | Q3 2025 |

---

## Historical Roadmap (v0.2.0, Completed)

*   ✅ Scaling Constitution
*   ✅ Autonomous MVP
*   ✅ Self-Improvement
*   ✅ Robustness
*   ✅ Architectural Health

---

## Takeaways

*   The immediate AI focus is **Phase 1.6: Dynamic Deduction**, which will make the system's reasoning smarter.
*   The next major user-facing epic is **v1.1: The Accessible Operator**, which will solve the issues of confusing commands and poor discoverability.
*   The project is on track for a **v1.0 release in Q1 2025**, followed by the major UX overhaul in Q2 2025.

---

## Contribute

*   For AI and systems engineers: **Phase 1.6: Dynamic Deduction** is the next big challenge.
*   For those interested in developer experience and accessibility: The tasks in **Epic v1.1** are perfect opportunities.
*   For beginners: **Phase 1.4: Cleanup** or the documentation task in **Phase 2.4** are perfect first issues.

✅ **Check GitHub issues to get started!**